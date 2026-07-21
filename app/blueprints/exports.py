"""
Exports blueprint – export individual messages as Markdown, PDF, or DOCX.

Every route verifies session ownership before serving content.
"""

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    jsonify,
)

from app.models import Attachment, Chat, Message
from app.services.export_service import (
    export_as_docx,
    export_as_markdown,
    export_as_pdf,
)
from app.utils.sanitize import sanitize_filename

exports_bp = Blueprint('exports', __name__)


def _get_owned_message(message_id):
    """Return the message if it belongs to the current session, else ``None``."""
    session_obj = g.current_session
    message = (
        Message.query
        .join(Chat, Message.chat_id == Chat.id)
        .filter(
            Message.id == message_id,
            Chat.session_id == session_obj.id,
        )
        .first()
    )
    return message


def _safe_download_name(message, extension):
    """Build a sanitised download filename from the parent chat title."""
    chat = Chat.query.get(message.chat_id)
    base = sanitize_filename(chat.title) if chat else 'export'
    return f'{base}_{message.id}.{extension}'


# ──────────────────────────────────────────────
#  Markdown export
# ──────────────────────────────────────────────

@exports_bp.route('/export/<int:message_id>/md')
def export_md(message_id):
    """Export a single message as a Markdown file."""
    message = _get_owned_message(message_id)
    if not message:
        return jsonify({'error': 'Message not found.'}), 404

    try:
        data = export_as_markdown(message.content)
        filename = _safe_download_name(message, 'md')
        return Response(
            data,
            mimetype='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
            },
        )
    except Exception as exc:
        current_app.logger.error('Markdown export failed for message %d: %s', message_id, exc)
        return jsonify({'error': 'Export failed.'}), 500


# ──────────────────────────────────────────────
#  PDF export
# ──────────────────────────────────────────────

@exports_bp.route('/export/<int:message_id>/pdf')
def export_pdf(message_id):
    """Export a single message as a PDF file."""
    message = _get_owned_message(message_id)
    if not message:
        return jsonify({'error': 'Message not found.'}), 404

    try:
        data = export_as_pdf(message.content)
        filename = _safe_download_name(message, 'pdf')
        return Response(
            data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
            },
        )
    except Exception as exc:
        current_app.logger.error('PDF export failed for message %d: %s', message_id, exc)
        return jsonify({'error': 'Export failed.'}), 500


# ──────────────────────────────────────────────
#  DOCX export
# ──────────────────────────────────────────────

@exports_bp.route('/export/<int:message_id>/docx')
def export_docx(message_id):
    """Export a single message as a DOCX file."""
    message = _get_owned_message(message_id)
    if not message:
        return jsonify({'error': 'Message not found.'}), 404

    try:
        data = export_as_docx(message.content)
        filename = _safe_download_name(message, 'docx')
        return Response(
            data,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
            },
        )
    except Exception as exc:
        current_app.logger.error('DOCX export failed for message %d: %s', message_id, exc)
        return jsonify({'error': 'Export failed.'}), 500
