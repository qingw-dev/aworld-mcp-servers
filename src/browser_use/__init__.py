"""RAG (Retrieval-Augmented Generation) System.

A comprehensive search and content processing system with AI agents,
web browsing capabilities, and various search services.
"""


# API Blueprints
from .api import (
    browser_bp,
    browser_router,
    browser_semaphore,
)

# Utilities
from .utils import (
    get_a_trace_with_img,
    get_a_trace_without_img,
    save_trace_in_oss,
    get_oss_client,
    list_traces,
    get_traces_from_oss,
)

# Public API - what gets imported with "from rag import *"
__all__ = [

    # API
    "browser_bp",
    "browser_router",
    "browser_semaphore",

    # Utilities
    "get_a_trace_with_img",
    "get_a_trace_without_img",
    "save_trace_in_oss",
    "get_oss_client",
    "list_traces",
    "get_traces_from_oss",
]
