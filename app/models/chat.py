"""
Chat model.

Represents a single conversation thread belonging to an anonymous session.
Each chat has its own title, optional system instruction, and a collection of messages.
"""

from datetime import datetime

from app.extensions import db


class Chat(db.Model):
    """A conversation thread with title, system instruction, and messages."""

    __tablename__ = 'chat'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('anonymous_session.id'),
        index=True,
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=True)
    system_instruction = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    archived = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    messages = db.relationship(
        'Message',
        backref='chat',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='Message.timestamp',
    )

    def __repr__(self):
        return f'<Chat {self.id} "{self.title}">'
