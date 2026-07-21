# MultiTool – Multi-Chat AI Application

A production-grade, multi-conversation AI web application built with Flask, SQLAlchemy, and the Google Gemini SDK. Features anonymous sessions, persistent storage, multimodal file handling, Markdown rendering, and export capabilities.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/shahram8708/MultiTool MultiTool
   cd MultiTool
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your GEMINI_API_KEY
   ```

5. **Initialize the database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   python app.py
   ```
   The application will be available at `http://localhost:5000`.

## Production Deployment

Use Gunicorn via the WSGI entry point:

```bash
gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 4
```

## Project Structure

```
MultiTool/
├── app/
│   ├── __init__.py          # Application factory
│   ├── extensions.py        # Flask extension instances
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # Blueprint route handlers
│   ├── services/            # Business logic (Gemini, files, export)
│   ├── utils/               # Session management, sanitization
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JS, images
├── config.py                # Configuration classes
├── app.py                   # Development entry point
├── wsgi.py                  # Production WSGI entry point
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── README.md
```

## License

MIT
