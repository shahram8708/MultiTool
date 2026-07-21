"""
Models package.

All models are imported here so that SQLAlchemy registers them
when the package is imported during app initialization.
"""

from app.models.session import AnonymousSession
from app.models.chat import Chat
from app.models.message import Message
from app.models.attachment import Attachment

__all__ = ['AnonymousSession', 'Chat', 'Message', 'Attachment']
