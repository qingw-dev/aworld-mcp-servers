"""RAG (Retrieval-Augmented Generation) System.

A comprehensive search and content processing system with AI agents,
web browsing capabilities, and various search services.
"""

# AI Agents
from .agents import (
    ReadingAgent,
    WebSearchAgent,
    web_search,
)

# API Blueprints
from .api import (
    health_bp,
    health_router,
    search_bp,
    search_router,
)

# Data Models
from .models import (
    AgenticSearchRequest,
    BatchSearchRequest,
    BatchSearchResponse,
    ErrorResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SingleSearchRequest,
    SingleSearchResponse,
    WebContent,
)

# Search Services
from .services import (
    ContentFetcherService,
    GoogleSearchService,
    SearchOrchestratorService,
)

# Utilities
from .utils import (
    extract_url_root_domain,
    get_clean_content,
    get_content_from_tag,
    get_response_from_llm,
)

# Version information
__version__ = "1.0.0"
__author__ = "Your Team"
__description__ = "RAG System for intelligent search and content processing"

# Public API - what gets imported with "from rag import *"
__all__ = [
    # Agents
    "ReadingAgent",
    "WebSearchAgent",
    "web_search",
    # Services
    "GoogleSearchService",
    "ContentFetcherService",
    "SearchOrchestratorService",
    # Models
    "SearchRequest",
    "SingleSearchRequest",
    "BatchSearchRequest",
    "AgenticSearchRequest",
    "SearchResponse",
    "SingleSearchResponse",
    "BatchSearchResponse",
    "HealthResponse",
    "ErrorResponse",
    "SearchResult",
    "WebContent",
    "SearchMetrics",
    # API
    "health_bp",
    "search_bp",
    "health_router",
    "search_router",
    # Utils
    "extract_url_root_domain",
    "get_clean_content",
    "get_content_from_tag",
    "get_response_from_llm",
]
