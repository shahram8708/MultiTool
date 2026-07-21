"""
Production WSGI entry point for the MultiTool application.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 4
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app('production')
