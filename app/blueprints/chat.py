"""
Chat blueprint – conversation management routes.

Handles: landing page, creating/renaming/deleting chats,
listing/searching chats, serving individual chat data, and health checks.
"""

from datetime import datetime, timezone

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    render_template,
    request,
)

from app.extensions import db
from app.models import Chat, Message
from app.utils.sanitize import sanitize_text, render_markdown_safe

chat_bp = Blueprint('chat', __name__)


# ──────────────────────────────────────────────
#  Landing page
# ──────────────────────────────────────────────

@chat_bp.route('/')
def index():
    """Render the main application page with the sidebar chat list and
    optionally an active conversation's messages."""
    session_obj = g.current_session
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('CHATS_PER_PAGE', 50)

    chats_pagination = (
        Chat.query
        .filter_by(session_id=session_obj.id, archived=False)
        .order_by(Chat.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    active_chat_id = request.args.get('chat_id', type=int)
    active_chat_obj = None
    messages_list = []

    if active_chat_id:
        active_chat_obj = Chat.query.filter_by(
            id=active_chat_id,
            session_id=session_obj.id,
            archived=False,
        ).first()
        if active_chat_obj:
            messages_list = (
                Message.query
                .filter_by(chat_id=active_chat_obj.id)
                .order_by(Message.timestamp.asc())
                .all()
            )

    chats_data = [
        {
            'id': c.id,
            'title': c.title,
            'updated_at': c.updated_at.isoformat() if c.updated_at else '',
        }
        for c in chats_pagination.items
    ]

    active_chat_data = None
    if active_chat_obj:
        active_chat_data = {
            'id': active_chat_obj.id,
            'title': active_chat_obj.title,
            'system_instruction': active_chat_obj.system_instruction or '',
            'created_at': active_chat_obj.created_at.isoformat() if active_chat_obj.created_at else '',
        }

    messages_data = []
    for msg in messages_list:
        msg_dict = {
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else '',
            'attachments': [
                {
                    'id': att.id,
                    'original_filename': att.original_filename,
                    'mime_type': att.mime_type,
                    'size': att.size,
                    'category': att.category,
                }
                for att in msg.attachments
            ],
        }
        if msg.role == 'assistant':
            msg_dict['rendered_content'] = render_markdown_safe(msg.content)
        messages_data.append(msg_dict)

    return render_template(
        'index.html',
        chats=chats_data,
        active_chat=active_chat_data,
        messages=messages_data,
        has_more_chats=chats_pagination.has_next,
        chats_page=page,
    )


# ──────────────────────────────────────────────
#  Create a new chat
# ──────────────────────────────────────────────

@chat_bp.route('/chat/new', methods=['POST'])
def new_chat():
    """Create a new chat conversation.

    Expects JSON body:
        {title: str, system_instruction?: str}
    """
    session_obj = g.current_session
    data = request.get_json(silent=True) or {}

    raw_title = (data.get('title') or '').strip()
    if not raw_title:
        return jsonify({'error': 'Title is required.'}), 400

    title = sanitize_text(raw_title, max_length=200)
    system_instruction = sanitize_text(
        (data.get('system_instruction') or '').strip(), max_length=10000
    )

    now = datetime.now(timezone.utc)
    chat = Chat(
        session_id=session_obj.id,
        title=title,
        system_instruction=system_instruction or None,
        created_at=now,
        updated_at=now,
        archived=False,
    )

    try:
        db.session.add(chat)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Failed to create chat: %s', exc)
        return jsonify({'error': 'Could not create chat.'}), 500

    return jsonify({
        'id': chat.id,
        'title': chat.title,
        'system_instruction': chat.system_instruction or '',
        'created_at': chat.created_at.isoformat(),
    }), 201


# ──────────────────────────────────────────────
#  Get single chat with messages
# ──────────────────────────────────────────────

@chat_bp.route('/chat/<int:chat_id>')
def get_chat(chat_id):
    """Return full chat data including ordered messages and their attachments."""
    session_obj = g.current_session
    chat = Chat.query.filter_by(
        id=chat_id, session_id=session_obj.id, archived=False
    ).first()

    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    messages = (
        Message.query
        .filter_by(chat_id=chat.id)
        .order_by(Message.timestamp.asc())
        .all()
    )

    messages_data = []
    for msg in messages:
        rendered_content = (
            render_markdown_safe(msg.content)
            if msg.role == 'assistant'
            else msg.content
        )
        attachments_data = [
            {
                'id': att.id,
                'original_filename': att.original_filename,
                'mime_type': att.mime_type,
                'size': att.size,
                'category': att.category,
            }
            for att in msg.attachments
        ]
        messages_data.append({
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'rendered_content': rendered_content,
            'timestamp': msg.timestamp.isoformat(),
            'attachments': attachments_data,
        })

    return jsonify({
        'chat': {
            'id': chat.id,
            'title': chat.title,
            'system_instruction': chat.system_instruction or '',
            'created_at': chat.created_at.isoformat(),
        },
        'messages': messages_data,
    })


# ──────────────────────────────────────────────
#  Rename a chat
# ──────────────────────────────────────────────

@chat_bp.route('/chat/<int:chat_id>/rename', methods=['PUT'])
def rename_chat(chat_id):
    """Rename an existing chat.

    Expects JSON body: {title: str}
    """
    session_obj = g.current_session
    chat = Chat.query.filter_by(
        id=chat_id, session_id=session_obj.id, archived=False
    ).first()

    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    data = request.get_json(silent=True) or {}
    raw_title = (data.get('title') or '').strip()
    if not raw_title:
        return jsonify({'error': 'Title is required.'}), 400

    chat.title = sanitize_text(raw_title, max_length=200)
    chat.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Failed to rename chat %d: %s', chat_id, exc)
        return jsonify({'error': 'Could not rename chat.'}), 500

    return jsonify({'success': True, 'title': chat.title})


@chat_bp.route('/chat/<int:chat_id>/settings', methods=['PUT'])
def update_chat_settings(chat_id):
    """Update chat title and/or system instruction.

    Expects JSON body with one or both keys:
        {title?: str, system_instruction?: str}
    """
    session_obj = g.current_session
    chat = Chat.query.filter_by(
        id=chat_id, session_id=session_obj.id, archived=False
    ).first()

    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    data = request.get_json(silent=True) or {}

    has_title = 'title' in data
    has_instruction = 'system_instruction' in data

    if not has_title and not has_instruction:
        return jsonify({'error': 'No changes provided.'}), 400

    if has_title:
        raw_title = (data.get('title') or '').strip()
        if not raw_title:
            return jsonify({'error': 'Title is required.'}), 400
        chat.title = sanitize_text(raw_title, max_length=200)

    if has_instruction:
        raw_instruction = (data.get('system_instruction') or '').strip()
        chat.system_instruction = (
            sanitize_text(raw_instruction, max_length=10000)
            if raw_instruction else None
        )

    chat.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Failed to update chat settings %d: %s', chat_id, exc)
        return jsonify({'error': 'Could not update chat settings.'}), 500

    return jsonify({
        'success': True,
        'chat': {
            'id': chat.id,
            'title': chat.title,
            'system_instruction': chat.system_instruction or '',
            'updated_at': chat.updated_at.isoformat() if chat.updated_at else '',
        },
    })


# ──────────────────────────────────────────────
#  Delete (soft) a chat
# ──────────────────────────────────────────────

@chat_bp.route('/chat/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Soft-delete a chat by setting archived=True."""
    session_obj = g.current_session
    chat = Chat.query.filter_by(
        id=chat_id, session_id=session_obj.id, archived=False
    ).first()

    if not chat:
        return jsonify({'error': 'Chat not found.'}), 404

    chat.archived = True
    chat.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Failed to archive chat %d: %s', chat_id, exc)
        return jsonify({'error': 'Could not delete chat.'}), 500

    return jsonify({'success': True})


# ──────────────────────────────────────────────
#  List chats (API / AJAX)
# ──────────────────────────────────────────────

@chat_bp.route('/api/chats')
def list_chats():
    """Return a paginated JSON list of the session's non-archived chats."""
    session_obj = g.current_session
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('CHATS_PER_PAGE', 50)

    pagination = (
        Chat.query
        .filter_by(session_id=session_obj.id, archived=False)
        .order_by(Chat.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    chats_data = []
    for chat in pagination.items:
        message_count = Message.query.filter_by(chat_id=chat.id).count()
        chats_data.append({
            'id': chat.id,
            'title': chat.title,
            'updated_at': chat.updated_at.isoformat(),
            'message_count': message_count,
        })

    return jsonify({
        'chats': chats_data,
        'has_next': pagination.has_next,
        'page': page,
    })


# ──────────────────────────────────────────────
#  Search chats
# ──────────────────────────────────────────────

@chat_bp.route('/api/chats/search')
def search_chats():
    """Search the session's chats by title (case-insensitive LIKE)."""
    session_obj = g.current_session
    query_str = request.args.get('q', '').strip()

    if not query_str:
        return jsonify({'chats': []})

    results = (
        Chat.query
        .filter_by(session_id=session_obj.id, archived=False)
        .filter(Chat.title.ilike(f'%{query_str}%'))
        .order_by(Chat.updated_at.desc())
        .limit(20)
        .all()
    )

    chats_data = [
        {
            'id': chat.id,
            'title': chat.title,
            'updated_at': chat.updated_at.isoformat(),
        }
        for chat in results
    ]

    return jsonify({'chats': chats_data})


# ──────────────────────────────────────────────
#  Health check
# ──────────────────────────────────────────────

@chat_bp.route('/health')
def health_check():
    """Simple liveness probe."""
    return jsonify({'status': 'ok'})
