"""
Application-wide error handlers.

Registers Flask error handlers for common HTTP error codes.
In production, error details are logged but not exposed to the client.
"""

from flask import current_app, jsonify, render_template, request


def register_error_handlers(app):
    """Attach error handlers for 404, 413, 429, and 500 to *app*."""

    def _wants_json():
        """Return True if the client prefers a JSON response."""
        return (
            request.accept_mimetypes.best_match(['application/json', 'text/html'])
            == 'application/json'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )

    # ── 404 Not Found ───────────────────────────

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return jsonify({'error': 'The requested resource was not found.'}), 404
        return render_template('errors/404.html'), 404

    # ── 413 Payload Too Large ───────────────────

    @app.errorhandler(413)
    def payload_too_large(error):
        if _wants_json():
            return jsonify({'error': 'The uploaded file is too large.'}), 413
        return render_template('errors/413.html'), 413

    # ── 429 Rate Limit Exceeded ─────────────────

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        if _wants_json():
            return jsonify({'error': 'Rate limit exceeded. Please slow down.'}), 429
        return render_template('errors/429.html'), 429

    # ── 500 Internal Server Error ───────────────

    @app.errorhandler(500)
    def internal_error(error):
        current_app.logger.error('Internal server error: %s', error)
        if _wants_json():
            return jsonify({'error': 'An unexpected error occurred.'}), 500
        return render_template('errors/500.html'), 500
