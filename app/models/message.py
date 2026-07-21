"""
Message model.

Represents a single message (user or assistant) within a chat.
Messages are ordered by timestamp and have an explicit ordering field.
"""

from datetime import datetime

from app.extensions import db


class Message(db.Model):
    """A single message within a chat conversation."""

    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chat_id = db.Column(
        db.Integer, db.ForeignKey('chat.id'), index=True, nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    ordering = db.Column(db.Integer, nullable=False, default=0)

    # Relationships
    attachments = db.relationship(
        'Attachment',
        backref='message',
        lazy='select',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<Message {self.id} [{self.role}] chat={self.chat_id}>'
