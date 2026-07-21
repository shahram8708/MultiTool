"""
Input sanitization and safe Markdown rendering utilities.

Provides functions to sanitize filenames, clamp user text length,
and render Markdown to bleach-sanitized HTML.
"""

import os
import re
import unicodedata

import bleach
import markdown as md_lib


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(filename: str) -> str:
    """Sanitize a user-supplied filename for safe filesystem storage.

    * Normalises Unicode (NFC).
    * Strips path separators so directory traversal is impossible.
    * Collapses whitespace and replaces spaces with underscores.
    * Removes characters that are problematic on Windows / Linux.
    * Truncates to 200 characters (excluding extension).
    * Falls back to ``'unnamed_file'`` if nothing usable remains.
    """
    if not filename:
        return 'unnamed_file'

    # Normalise Unicode
    filename = unicodedata.normalize('NFC', filename)

    # Strip any directory components
    filename = os.path.basename(filename)

    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)

    # Remove characters that are unsafe on Windows
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Collapse whitespace and replace with underscores
    filename = re.sub(r'\s+', '_', filename).strip('_.')

    # Split name and extension for length capping
    if '.' in filename:
        name, ext = filename.rsplit('.', 1)
        name = name[:200]
        filename = f'{name}.{ext}'
    else:
        filename = filename[:200]

    return filename if filename else 'unnamed_file'


# ---------------------------------------------------------------------------
# Text sanitization
# ---------------------------------------------------------------------------

def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize and clamp user-supplied text.

    * Strips leading/trailing whitespace.
    * Removes null bytes.
    * Truncates to *max_length* characters.
    """
    if not text:
        return ''

    text = text.strip()
    text = text.replace('\x00', '')

    if len(text) > max_length:
        text = text[:max_length]

    return text


# ---------------------------------------------------------------------------
# Safe Markdown rendering
# ---------------------------------------------------------------------------

# Allowed HTML tags and attributes after bleach sanitization
_ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'ul', 'ol', 'li',
    'strong', 'em', 'b', 'i', 'u', 's', 'del', 'mark', 'sub', 'sup',
    'a',
    'code', 'pre', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
    'div', 'span',
    'details', 'summary',
    'dl', 'dt', 'dd',
]

_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'th': ['align', 'scope'],
    'td': ['align'],
    'code': ['class'],
    'pre': ['class'],
    'div': ['class'],
    'span': ['class'],
}


def render_markdown_safe(md_text: str) -> str:
    """Render Markdown to sanitized HTML.

    1. Convert Markdown → HTML using the ``markdown`` library with
       ``fenced_code``, ``tables``, ``nl2br``, and ``sane_lists`` extensions.
    2. Pass the resulting HTML through ``bleach.clean`` to strip any
       dangerous tags, attributes, or scripts.

    Returns safe HTML suitable for embedding in a Jinja2 template
    via ``{{ content | safe }}``.
    """
    if not md_text:
        return ''

    # Step 1: Markdown → HTML
    raw_html = md_lib.markdown(
        md_text,
        extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists'],
    )

    # Step 2: Bleach sanitization
    safe_html = bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )

    return safe_html
