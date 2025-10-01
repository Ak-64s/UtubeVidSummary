"""Expose the Flask WSGI app for Vercel's Python runtime."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app  # noqa: E402  pylint: disable=wrong-import-position

# Vercel automatically detects the module-level `app` callable for WSGI apps.
__all__ = ["app"]
