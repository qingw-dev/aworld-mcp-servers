"""API routes for the search service."""

from .browser_pool import browser_semaphore
from .browser import browser_bp
from .browser_fastapi import browser_router

__all__ = ["browser_semaphore","browser_bp", "browser_router"]