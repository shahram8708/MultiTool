"""
File handling service.

Validates, saves, categorises, and prepares uploaded files for the Gemini API.
Supports images, PDFs, audio, video, spreadsheets, Word documents, and
plain-text files.
"""

import io
import mimetypes
import os
import tempfile
from uuid import uuid4

from flask import current_app
from google import genai
from google.genai import types
from PIL import Image

from app.services.gemini_service import get_gemini_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: set[str] = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'ico',
    # Documents
    'pdf', 'doc', 'docx', 'txt', 'md', 'rtf', 'csv', 'tsv',
    # Spreadsheets
    'xls', 'xlsx',
    # Audio
    'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a',
    # Video
    'mp4', 'webm', 'avi', 'mov', 'mkv',
    # Code / config
    'json', 'xml', 'yaml', 'yml', 'py', 'js', 'html', 'css',
}

MAX_FILES_PER_MESSAGE: int = 5

# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, str] = {
    'image': 'image',
    'audio': 'audio',
    'video': 'video',
}

_EXT_CATEGORY_OVERRIDE: dict[str, str] = {
    'pdf': 'pdf',
    'doc': 'document',
    'docx': 'document',
    'rtf': 'document',
    'xls': 'spreadsheet',
    'xlsx': 'spreadsheet',
    'csv': 'spreadsheet',
    'tsv': 'spreadsheet',
}


def detect_category(mime_type: str, extension: str) -> str:
    """Return a human-friendly file category string.

    Categories: image, pdf, spreadsheet, document, audio, video, text, other.
    """
    ext = extension.lower().lstrip('.')

    # Extension-based overrides take priority for ambiguous MIME types
    if ext in _EXT_CATEGORY_OVERRIDE:
        return _EXT_CATEGORY_OVERRIDE[ext]

    if mime_type:
        prefix = mime_type.split('/')[0]
        if prefix in _CATEGORY_MAP:
            return _CATEGORY_MAP[prefix]
        if 'text' in mime_type or 'json' in mime_type or 'xml' in mime_type:
            return 'text'

    # Fallback for known text-like extensions
    if ext in {'txt', 'md', 'json', 'xml', 'yaml', 'yml', 'py', 'js', 'html', 'css'}:
        return 'text'

    return 'other'


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file(file) -> tuple[bool, str]:
    """Validate an uploaded file's extension and MIME type.

    Returns
    -------
    tuple[bool, str]
        ``(True, '')`` on success or ``(False, reason)`` on failure.
    """
    if not file or not file.filename:
        return False, 'No file provided.'

    filename = file.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext not in ALLOWED_EXTENSIONS:
        return False, f'File type ".{ext}" is not allowed.'

    # Check MIME type
    mime_type = file.content_type or mimetypes.guess_type(filename)[0] or ''
    if not mime_type:
        return False, 'Could not determine file type.'

    # Size check (read position, check, then seek back)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    max_size = current_app.config.get('MAX_FILE_SIZE', 25 * 1024 * 1024)
    if size > max_size:
        return False, (
            f'File is too large ({size / (1024 * 1024):.1f} MB). '
            f'Maximum allowed is {max_size / (1024 * 1024):.0f} MB.'
        )

    return True, ''


# ---------------------------------------------------------------------------
# Upload and storage
# ---------------------------------------------------------------------------

def save_upload(file, upload_dir: str) -> dict:
    """Save an uploaded file to *upload_dir* with a collision-proof name.

    Returns
    -------
    dict
        Keys: original_filename, stored_filename, file_path, mime_type,
        size, category.
    """
    os.makedirs(upload_dir, exist_ok=True)

    original_filename = file.filename
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    stored_filename = f'{uuid4().hex}.{ext}' if ext else uuid4().hex

    file_path = os.path.join(upload_dir, stored_filename)

    file.seek(0)
    file.save(file_path)

    size = os.path.getsize(file_path)
    mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'
    category = detect_category(mime_type, ext)

    return {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'file_path': file_path,
        'mime_type': mime_type,
        'size': size,
        'category': category,
    }


# ---------------------------------------------------------------------------
# Gemini preparation helpers
# ---------------------------------------------------------------------------

def _prepare_image(attachment, upload_dir: str) -> list[types.Part]:
    """Load an image and return it as an inline Part."""
    path = os.path.join(upload_dir, attachment.stored_filename)
    try:
        img = Image.open(path)
        # Convert RGBA/palette images to RGB for JPEG-compatible bytes
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        buf = io.BytesIO()
        fmt = 'PNG' if attachment.mime_type and 'png' in attachment.mime_type else 'JPEG'
        img.save(buf, format=fmt)
        buf.seek(0)
        mime = f'image/{fmt.lower()}'
        return [types.Part.from_bytes(data=buf.read(), mime_type=mime)]
    except Exception as exc:
        current_app.logger.error('Failed to prepare image %s: %s', path, exc)
        return [types.Part.from_text(text=f'[Image: {attachment.original_filename} could not be processed]')]


def _prepare_pdf(attachment, upload_dir: str) -> list[types.Part]:
    """Rasterise each page of a PDF to an image Part using PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    path = os.path.join(upload_dir, attachment.stored_filename)
    parts: list[types.Part] = []
    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes('png')
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type='image/png'))
        doc.close()
    except Exception as exc:
        current_app.logger.error('Failed to rasterize PDF %s: %s', path, exc)
        parts.append(
            types.Part.from_text(text=f'[PDF: {attachment.original_filename} could not be processed]')
        )
    return parts


def _prepare_audio_video(attachment, upload_dir: str) -> list[types.Part]:
    """Upload an audio or video file via the Gemini Files API."""
    path = os.path.join(upload_dir, attachment.stored_filename)
    try:
        client = get_gemini_client()
        uploaded = client.files.upload(
            file=path,
            config=types.UploadFileConfig(
                mime_type=attachment.mime_type,
                display_name=attachment.original_filename,
            ),
        )
        return [types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)]
    except Exception as exc:
        current_app.logger.error(
            'Failed to upload media %s to Gemini: %s', path, exc
        )
        return [
            types.Part.from_text(
                text=f'[Media: {attachment.original_filename} could not be uploaded]'
            )
        ]


def _prepare_spreadsheet(attachment, upload_dir: str) -> list[types.Part]:
    """Extract text content from Excel/CSV files."""
    import pandas as pd

    path = os.path.join(upload_dir, attachment.stored_filename)
    try:
        ext = attachment.stored_filename.rsplit('.', 1)[-1].lower()
        if ext == 'csv':
            df = pd.read_csv(path, nrows=500)
        elif ext == 'tsv':
            df = pd.read_csv(path, sep='\t', nrows=500)
        elif ext in ('xls', 'xlsx'):
            df = pd.read_excel(path, nrows=500, engine='openpyxl')
        else:
            df = pd.read_csv(path, nrows=500)

        text_repr = (
            f'Spreadsheet: {attachment.original_filename}\n'
            f'Shape: {df.shape[0]} rows × {df.shape[1]} columns\n'
            f'Columns: {", ".join(df.columns.astype(str))}\n\n'
            f'{df.to_string(index=False, max_rows=100)}'
        )
        return [types.Part.from_text(text=text_repr)]
    except Exception as exc:
        current_app.logger.error('Failed to read spreadsheet %s: %s', path, exc)
        return [
            types.Part.from_text(
                text=f'[Spreadsheet: {attachment.original_filename} could not be read]'
            )
        ]


def _prepare_document(attachment, upload_dir: str) -> list[types.Part]:
    """Extract text from Word documents."""
    from docx import Document as DocxDocument

    path = os.path.join(upload_dir, attachment.stored_filename)
    try:
        doc = DocxDocument(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = '\n\n'.join(paragraphs)
        header = f'Document: {attachment.original_filename}\n\n'
        return [types.Part.from_text(text=header + text)]
    except Exception as exc:
        current_app.logger.error('Failed to read document %s: %s', path, exc)
        return [
            types.Part.from_text(
                text=f'[Document: {attachment.original_filename} could not be read]'
            )
        ]


def _prepare_text(attachment, upload_dir: str) -> list[types.Part]:
    """Read plain-text or code files."""
    path = os.path.join(upload_dir, attachment.stored_filename)
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read(100_000)  # cap at ~100 KB of text
        header = f'File: {attachment.original_filename}\n\n'
        return [types.Part.from_text(text=header + content)]
    except Exception as exc:
        current_app.logger.error('Failed to read text file %s: %s', path, exc)
        return [
            types.Part.from_text(
                text=f'[File: {attachment.original_filename} could not be read]'
            )
        ]


# ---------------------------------------------------------------------------
# Public preparation entry point
# ---------------------------------------------------------------------------

def prepare_for_gemini(attachment, upload_dir: str) -> list[types.Part]:
    """Convert an :class:`Attachment` into a list of Gemini ``Part`` objects.

    Dispatches to a category-specific handler:

    * **image** – loaded directly as inline image bytes.
    * **pdf** – each page rasterised to PNG via PyMuPDF.
    * **audio / video** – uploaded to the Gemini Files API.
    * **spreadsheet** – text extracted with pandas / openpyxl.
    * **document** – text extracted with python-docx.
    * **text** – read as UTF-8 text.
    * **other** – best-effort text read.
    """
    category = attachment.category

    handlers = {
        'image': _prepare_image,
        'pdf': _prepare_pdf,
        'audio': _prepare_audio_video,
        'video': _prepare_audio_video,
        'spreadsheet': _prepare_spreadsheet,
        'document': _prepare_document,
        'text': _prepare_text,
    }

    handler = handlers.get(category, _prepare_text)
    return handler(attachment, upload_dir)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_temp_files(paths: list[str]) -> None:
    """Delete a list of temporary file paths, logging errors silently."""
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as exc:
            current_app.logger.warning('Failed to delete temp file %s: %s', path, exc)
