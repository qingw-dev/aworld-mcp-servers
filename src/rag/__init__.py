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

# Search Services
from .services import (
    GoogleSearchService,
    ContentFetcherService,
    SearchOrchestratorService,
)

# Data Models
from .models import (
    SearchRequest,
    SingleSearchRequest,
    BatchSearchRequest,
    AgenticSearchRequest,
    SearchResponse,
    SingleSearchResponse,
    BatchSearchResponse,
    HealthResponse,
    ErrorResponse,
    SearchResult,
    WebContent,
)

# API Blueprints
from .api import (
    health_bp,
    search_bp,
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
    # Core
    "Settings",
    "get_settings",
    "setup_logging",
    "get_logger",
    "MetricsCollector",
    "get_metrics_collector",
    
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
    
    # Utils
    "extract_url_root_domain",
    "get_clean_content",
    "get_content_from_tag",
    "get_response_from_llm",
]

# Convenience functions for common use cases
def create_search_agent(config: dict = None) -> WebSearchAgent:
    """Create a configured web search agent.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured WebSearchAgent instance
    """
    settings = get_settings()
    if config:
        # Merge with default settings
        pass
    return WebSearchAgent()

def create_reading_agent(config: dict = None) -> ReadingAgent:
    """Create a configured reading agent.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured ReadingAgent instance
    """
    settings = get_settings()
    if config:
        # Merge with default settings
        pass
    return ReadingAgent()

def initialize_rag_system(config_path: str = None) -> dict:
    """Initialize the complete RAG system.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary with initialized components
    """
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    # Load settings
    settings = get_settings()
    
    # Initialize metrics
    metrics = get_metrics_collector()
    
    logger.info("RAG system initialized successfully")
    
    return {
        "settings": settings,
        "logger": logger,
        "metrics": metrics,
        "search_agent": create_search_agent(),
        "reading_agent": create_reading_agent(),
    }