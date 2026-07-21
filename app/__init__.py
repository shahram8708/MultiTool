"""
MultiTool Application Factory
Production-ready Flask application with anonymous sessions, multi-chat AI,
file uploads, and export capabilities.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, g, session

from app.extensions import db, migrate, csrf, limiter
from config import config


def create_app(config_name='development'):
    """Create and configure the Flask application.

    Args:
        config_name: Configuration key – 'development', 'testing', or 'production'.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(config[config_name])

    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if database_uri.startswith('sqlite:///'):
        db_path = database_uri.replace('sqlite:///', '', 1)
        if database_uri.startswith('sqlite:////'):
            db_path = '/' + db_path.lstrip('/')
        db_path = os.path.expanduser(db_path)
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(os.path.join(app.root_path, db_path))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # ---------------------
    # Initialize extensions
    # ---------------------
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # ---------------------
    # Register models so Alembic / create_all can see them
    # ---------------------
    from app.models import AnonymousSession, Chat, Message, Attachment  # noqa: F401

    # ---------------------
    # Register blueprints
    # ---------------------
    from app.blueprints.chat import chat_bp
    from app.blueprints.messaging import messaging_bp
    from app.blueprints.uploads import uploads_bp
    from app.blueprints.exports import exports_bp

    app.register_blueprint(chat_bp, url_prefix='')
    app.register_blueprint(messaging_bp, url_prefix='')
    app.register_blueprint(uploads_bp, url_prefix='')
    app.register_blueprint(exports_bp, url_prefix='')

    # ---------------------
    # Register error handlers
    # ---------------------
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # ---------------------
    # Logging
    # ---------------------
    _configure_logging(app, config_name)

    # ---------------------
    # Before-request hook: anonymous session management
    # ---------------------
    @app.before_request
    def _load_session():
        """Ensure every request has a valid anonymous session."""
        from app.utils.session_manager import get_or_create_session

        session.permanent = True
        g.current_session = get_or_create_session()

    # ---------------------
    # Create database tables & upload folder
    # ---------------------
    with app.app_context():
        db.create_all()

        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)

    return app


def _configure_logging(app, config_name):
    """Set up console and (in production) file-based rotating log handlers."""

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    # Console handler – always present
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if config_name != 'production' else logging.INFO)
    app.logger.addHandler(console_handler)

    # File handler – production only
    if config_name == 'production':
        log_dir = os.path.join(app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'multitool.log'),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.DEBUG if config_name != 'production' else logging.INFO)
