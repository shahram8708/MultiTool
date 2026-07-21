"""
Development entry point for the MultiTool application.

Usage:
    python app.py
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5000)
