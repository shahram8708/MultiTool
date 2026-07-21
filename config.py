"""
Application configuration classes.

Provides Base, Development, Production, and Testing configurations.
All sensitive values are loaded from environment variables.
"""

import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared across all environments."""

    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)

    # Database
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('sqlite:///'):
        db_path = database_url[10:]
        if not os.path.isabs(db_path):
            database_url = 'sqlite:///' + os.path.abspath(os.path.join(basedir, db_path))
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///' + os.path.join(basedir, 'instance', 'multitool.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini AI
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')

    # File Uploads
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
    MAX_FILES_PER_MESSAGE = 5

    # Pagination
    MESSAGES_PER_PAGE = 50
    CHATS_PER_PAGE = 50


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production-specific configuration."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(Config):
    """Testing-specific configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
