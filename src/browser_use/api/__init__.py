"""API routes for the search service."""

from .browser import browser_bp
from .browser_fastapi import browser_router

__all__ = ["browser_bp", "browser_router"]