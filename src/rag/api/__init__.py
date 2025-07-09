"""API routes for the search service."""

from .health import health_bp
from .search import search_bp
from .health_fastapi import health_router
from .search_fastapi import search_router

__all__ = ["health_bp", "search_bp", "health_router", "search_router"]