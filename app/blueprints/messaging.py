"""
Messaging blueprint – sending messages, regenerating responses.

Handles multipart form-data with file attachments, Gemini AI integration,
and message ordering.
"""

from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    request,
)

from app.extensions import csrf, db, limiter
from app.models import Attachment, Chat, Message
from app.services.gemini_service import send_message as gemini_send
from app.services.file_service import (
    cleanup_temp_files,
    prepare_for_gemini,
    save_upload,
    validate_file,
)
from app.utils.sanitize import render_markdown_safe, sanitize_text

messaging_bp = Blueprint('messaging', __name__)


def _verify_chat_ownership(chat_id):
    """Return the chat if it belongs to the current session and is not
    archived, otherwise ``None``."""
    return Chat.query.filter_by(
        id=chat_id,
        session_id=g.current_session.id,
        archived=False,
    ).first()


def _next_ordering(chat_id):
    """Return the next ordering integer for a message in *chat_id*."""
    last = (
        db.session.query(db.func.max(Message.ordering))
        .filter_by(chat_id=chat_id)
        .scalar()
    )
    return (last or 0) + 1


def _serialize_attachment(att):
    return {
        'id': att.id,
        'original_filename': att.original_filename,
        'mime_type': att.mime_type,
        'size': att.size,
        'category': att.category,
    }


# ──────────────────────────────────────────────
#  Send a message (with optional file uploads)
# ──────────────────────────────────────────────

@messaging_bp.route('/chat/<int:chat_id>/send', methods=['POST'])
@csrf.exempt
@limiter.limit('30 per minute')
def send_message_route(chat_id):
    """Accept user text + optional files, relay to Gemini, persist both
    user and assistant messages, and return JSON."""
    chat = _verify_chat_ownership(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    # ── Collect inputs ──────────────────────────
    raw_text = (request.form.get('message') or '').strip()
    files = request.files.getlist('files')
    max_files = current_app.config.get('MAX_FILES_PER_MESSAGE', 5)

    if not raw_text and not files:
        return jsonify({'error': 'Message text or at least one file is required.'}), 400

    text = sanitize_text(raw_text, max_length=10000) if raw_text else ''

    if len(files) > max_files:
        return jsonify({
            'error': f'Maximum {max_files} files per message.',
        }), 400

    upload_dir = current_app.config['UPLOAD_FOLDER']

    # ── Validate & save files ───────────────────
    saved_infos = []
    temp_paths = []
    for f in files:
        valid, reason = validate_file(f)
        if not valid:
            cleanup_temp_files(temp_paths)
            return jsonify({'error': f'File "{f.filename}" rejected: {reason}'}), 400
        info = save_upload(f, upload_dir)
        saved_infos.append(info)
        temp_paths.append(info['file_path'])

    # Determine whether this is the first interaction in the chat.
    existing_message_count = Message.query.filter_by(chat_id=chat_id).count()
    include_system_instruction = existing_message_count == 0

    # ── Persist user message ────────────────────
    ordering = _next_ordering(chat_id)
    now = datetime.now(timezone.utc)

    user_msg = Message(
        chat_id=chat_id,
        role='user',
        content=text,
        timestamp=now,
        ordering=ordering,
    )

    try:
        db.session.add(user_msg)
        db.session.flush()  # obtain user_msg.id for attachments

        attachments = []
        for info in saved_infos:
            att = Attachment(
                message_id=user_msg.id,
                original_filename=info['original_filename'],
                stored_filename=info['stored_filename'],
                file_path=info['file_path'],
                mime_type=info['mime_type'],
                size=info['size'],
                category=info['category'],
            )
            db.session.add(att)
            attachments.append(att)

        db.session.flush()  # get attachment ids

        # ── Prepare Gemini file parts ───────────
        file_parts = []
        for att in attachments:
            try:
                parts = prepare_for_gemini(att, upload_dir)
                file_parts.extend(parts)
            except Exception as exc:
                current_app.logger.warning(
                    'Could not prepare attachment %s for Gemini: %s',
                    att.original_filename,
                    exc,
                )

        # ── Call Gemini ─────────────────────────
        assistant_text = None
        gemini_error = None
        try:
            assistant_text = gemini_send(
                chat_id,
                text,
                file_parts if file_parts else None,
                include_system_instruction=include_system_instruction,
                exclude_message_id=user_msg.id,
            )
        except Exception as exc:
            current_app.logger.error('Gemini API error for chat %d: %s', chat_id, exc)
            gemini_error = str(exc)

        # ── Persist assistant message (if available) ──
        assistant_msg_data = None
        if assistant_text:
            assistant_msg = Message(
                chat_id=chat_id,
                role='assistant',
                content=assistant_text,
                timestamp=datetime.now(timezone.utc),
                ordering=ordering + 1,
            )
            db.session.add(assistant_msg)

        chat.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # ── Build response ──────────────────────
        user_msg_data = {
            'id': user_msg.id,
            'content': user_msg.content,
            'timestamp': user_msg.timestamp.isoformat(),
            'attachments': [_serialize_attachment(a) for a in attachments],
        }

        if assistant_text:
            assistant_msg_data = {
                'id': assistant_msg.id,
                'content': assistant_msg.content,
                'rendered_content': render_markdown_safe(assistant_msg.content),
                'timestamp': assistant_msg.timestamp.isoformat(),
            }

        response = {'user_message': user_msg_data}
        if assistant_msg_data:
            response['assistant_message'] = assistant_msg_data
        elif gemini_error:
            response['assistant_error'] = gemini_error

        return jsonify(response), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            'Error processing message for chat %d: %s', chat_id, exc
        )
        return jsonify({'error': 'Failed to process message.'}), 500


# ──────────────────────────────────────────────
#  Regenerate the last assistant response
# ──────────────────────────────────────────────

@messaging_bp.route('/chat/<int:chat_id>/regenerate', methods=['POST'])
@limiter.limit('10 per minute')
def regenerate_response(chat_id):
    """Delete the last assistant message and re-generate from Gemini."""
    chat = _verify_chat_ownership(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    # Find last assistant message
    last_assistant = (
        Message.query
        .filter_by(chat_id=chat_id, role='assistant')
        .order_by(Message.ordering.desc())
        .first()
    )

    if not last_assistant:
        return jsonify({'error': 'No assistant message to regenerate.'}), 404

    # Find last user message (the one that prompted the assistant reply)
    last_user = (
        Message.query
        .filter_by(chat_id=chat_id, role='user')
        .order_by(Message.ordering.desc())
        .first()
    )

    if not last_user:
        return jsonify({'error': 'No user message found.'}), 404

    deleted_ordering = last_assistant.ordering

    try:
        db.session.delete(last_assistant)
        db.session.flush()

        # Re-call Gemini (files are not re-sent on regeneration)
        assistant_text = gemini_send(
            chat_id,
            last_user.content,
            None,
            include_system_instruction=False,
        )

        new_assistant = Message(
            chat_id=chat_id,
            role='assistant',
            content=assistant_text,
            timestamp=datetime.now(timezone.utc),
            ordering=deleted_ordering,
        )
        db.session.add(new_assistant)

        chat.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            'assistant_message': {
                'id': new_assistant.id,
                'content': new_assistant.content,
                'rendered_content': render_markdown_safe(new_assistant.content),
                'timestamp': new_assistant.timestamp.isoformat(),
            }
        })

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            'Regeneration failed for chat %d: %s', chat_id, exc
        )
        return jsonify({'error': 'Failed to regenerate response.'}), 500
