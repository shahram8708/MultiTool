"""
Anonymous session manager.

Handles creating and retrieving ``AnonymousSession`` records tied to the
visitor's Flask session cookie.  Each visitor gets a persistent UUID stored
in ``flask.session['visitor_id']``.
"""

from datetime import datetime
from uuid import uuid4

from flask import session

from app.extensions import db
from app.models.session import AnonymousSession


def get_or_create_session() -> AnonymousSession:
    """Return the :class:`AnonymousSession` for the current visitor.

    If the visitor already has a ``visitor_id`` in their Flask session cookie
    **and** a matching database record exists, that record is returned with
    its ``last_active`` timestamp refreshed.

    Otherwise a new ``AnonymousSession`` is created, persisted, and the
    ``visitor_id`` cookie is set.
    """
    visitor_id = session.get('visitor_id')

    if visitor_id:
        anon_session = AnonymousSession.query.filter_by(uuid=visitor_id).first()
        if anon_session:
            anon_session.last_active = datetime.utcnow()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return anon_session

    # Create a new anonymous session
    new_uuid = str(uuid4())
    anon_session = AnonymousSession(uuid=new_uuid)
    db.session.add(anon_session)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # Store the UUID in the Flask session cookie
    session['visitor_id'] = new_uuid
    session.permanent = True  # use PERMANENT_SESSION_LIFETIME from config

    return anon_session
