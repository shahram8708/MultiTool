"""
Uploads blueprint – serve user-uploaded files securely.

Files are only served if the requesting session owns the attachment.
"""

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    send_from_directory,
)

from app.models import Attachment, Chat, Message

uploads_bp = Blueprint('uploads', __name__)


@uploads_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve a previously uploaded file after verifying session ownership.

    The lookup joins Attachment → Message → Chat to confirm the file
    belongs to a chat owned by the current anonymous session.
    """
    session_obj = g.current_session

    attachment = (
        Attachment.query
        .join(Message, Attachment.message_id == Message.id)
        .join(Chat, Message.chat_id == Chat.id)
        .filter(
            Attachment.stored_filename == filename,
            Chat.session_id == session_obj.id,
        )
        .first()
    )

    if not attachment:
        return jsonify({'error': 'File not found.'}), 404

    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        filename,
    )
