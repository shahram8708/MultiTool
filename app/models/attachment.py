"""
Attachment model.

Represents a file attached to a message. Stores metadata about the uploaded file
including its storage location, MIME type, size, and content category.
"""

from app.extensions import db


class Attachment(db.Model):
    """A file attachment associated with a message."""

    __tablename__ = 'attachment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey('message.id'), index=True, nullable=False
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    size = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(50), nullable=False, default='other')
    processing_metadata = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Attachment {self.id} "{self.original_filename}" ({self.category})>'
