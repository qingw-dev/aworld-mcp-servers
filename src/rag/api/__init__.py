"""API routes for the search service."""

from .health import health_bp
from .search import search_bp

__all__ = ["health_bp", "search_bp"]