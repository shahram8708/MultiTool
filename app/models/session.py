"""
AnonymousSession model.

Tracks anonymous visitors via a UUID stored in their session cookie.
Each visitor can have multiple chats.
"""

from datetime import datetime

from app.extensions import db


class AnonymousSession(db.Model):
    """Represents an anonymous visitor session identified by a UUID cookie."""

    __tablename__ = 'anonymous_session'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.String(36), unique=True, index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    chats = db.relationship(
        'Chat',
        backref='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<AnonymousSession {self.uuid[:8]}…>'
