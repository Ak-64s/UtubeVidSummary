"""
Security middleware for adding HTTP security headers.
"""
import os
from flask import Flask, Response


def configure_security_headers(app: Flask) -> None:
    """
    Configure security headers for all HTTP responses.
    
    Args:
        app: Flask application instance
    """
    
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Add security headers to every response."""
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers.setdefault('Content-Security-Policy', csp)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        if os.getenv('ENABLE_HSTS', 'false').lower() == 'true':
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=63072000; includeSubDomains; preload'
            )
        
        return response
