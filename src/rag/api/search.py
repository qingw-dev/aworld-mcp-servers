"""Search API routes."""

import uuid
from flask import Blueprint, request, jsonify, g
from pydantic import ValidationError

from ..core.logging import get_logger
from ..core.metrics import get_metrics_collector
from ..models.requests import (
    SearchRequest,
    SingleSearchRequest,
    BatchSearchRequest,
    AgenticSearchRequest,
)
from ..models.responses import ErrorResponse
from ..services.search_orchestrator import SearchOrchestratorService

search_bp = Blueprint("search", __name__, url_prefix="/search")
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


@search_bp.before_request
def add_request_id():
    """Add unique request ID to each search request."""
    g.request_id = str(uuid.uuid4())[:8]


@search_bp.errorhandler(ValidationError)
def handle_validation_error(error: ValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(f"[{g.request_id}] Validation error: {error}")
    response = ErrorResponse(
        request_id=g.request_id,
        error="Validation error",
        details=str(error),
    )
    return jsonify(response.model_dump()), 400


@search_bp.errorhandler(Exception)
def handle_general_error(error: Exception):
    """Handle general exceptions."""
    logger.error(f"[{g.request_id}] Unexpected error: {error}")
    response = ErrorResponse(
        request_id=g.request_id,
        error="Internal server error",
        details="An unexpected error occurred",
    )
    return jsonify(response.model_dump()), 500


@search_bp.route("", methods=["POST"])
@metrics_collector.log_performance
def search_endpoint():
    """Main search endpoint for multi-query searches.
    
    Expected JSON payload:
    {
        "api_key": "your_google_api_key",
        "cse_id": "your_google_cse_id",
        "queries": ["query1", "query2", ...],
        "num_results": 5,  // optional
        "language": "en",  // optional
        "country": "US",   // optional
        "safe_search": true,  // optional
        "max_len": 8192  // optional
    }
    """
    if not request.is_json:
        logger.warning(f"[{g.request_id}] Non-JSON request received")
        response = ErrorResponse(
            request_id=g.request_id,
            error="Request must be JSON",
        )
        return jsonify(response.model_dump()), 400
    
    try:
        # Validate request
        search_request = SearchRequest(**request.get_json())
        
        # Process search
        orchestrator = SearchOrchestratorService()
        response = orchestrator.process_search_request(search_request, g.request_id)
        
        return jsonify(response.model_dump())
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in search endpoint: {e}")
        raise e  # Will be handled by the error handler


@search_bp.route("/single", methods=["POST"])
@metrics_collector.log_performance
def single_search_endpoint():
    """Simplified endpoint for single query searches.
    
    Expected JSON payload:
    {
        "api_key": "your_google_api_key",
        "cse_id": "your_google_cse_id",
        "query": "search term",
        "num_results": 5,  // optional
        "fetch_content": true,  // optional
        "language": "en",  // optional
        "country": "US",   // optional
        "safe_search": true,  // optional
        "max_len": 8192  // optional
    }
    """
    if not request.is_json:
        logger.warning(f"[{g.request_id}] Non-JSON request received")
        response = ErrorResponse(
            request_id=g.request_id,
            error="Request must be JSON",
        )
        return jsonify(response.model_dump()), 400
    
    try:
        # Validate request
        search_request = SingleSearchRequest(**request.get_json())
        
        # Process search
        orchestrator = SearchOrchestratorService()
        response = orchestrator.process_single_search_request(search_request, g.request_id)
        
        return jsonify(response.model_dump())
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in single search endpoint: {e}")
        raise e  # Will be handled by the error handler


@search_bp.route("/batch", methods=["POST"])
@metrics_collector.log_performance
def batch_search_endpoint():
    """Batch search endpoint for multiple queries with different credentials.
    
    Expected JSON payload:
    {
        "searches": [
            {
                "api_key": "api_key_1",
                "cse_id": "cse_id_1",
                "query": "search term 1",
                "num_results": 5,
                "max_len": 8192  // optional
            }
        ],
        "fetch_content": true  // optional
    }
    """
    if not request.is_json:
        logger.warning(f"[{g.request_id}] Non-JSON request received")
        response = ErrorResponse(
            request_id=g.request_id,
            error="Request must be JSON",
        )
        return jsonify(response.model_dump()), 400
    
    try:
        # Validate request
        search_request = BatchSearchRequest(**request.get_json())
        
        # Process search
        orchestrator = SearchOrchestratorService()
        response = orchestrator.process_batch_search_request(search_request, g.request_id)
        
        return jsonify(response.model_dump())
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in batch search endpoint: {e}")
        raise e  # Will be handled by the error handler


@search_bp.route("/agentic", methods=["POST"])
@metrics_collector.log_performance
def agentic_search_endpoint():
    """Agentic search endpoint using the existing search handler.
    
    Expected JSON payload:
    {
        "question": "user question",
        "search_queries": ["query1", "query2"],
        "base_url": "openai_api_base_url",
        "api_key": "openai_api_key",
        "serper_api_key": "serper_api_key",
        "topk": 5  // optional
    }
    """
    if not request.is_json:
        logger.warning(f"[{g.request_id}] Non-JSON request received")
        response = ErrorResponse(
            request_id=g.request_id,
            error="Request must be JSON",
        )
        return jsonify(response.model_dump()), 400
    
    try:
        # Validate request
        search_request = AgenticSearchRequest(**request.get_json())
        
        # Process search
        orchestrator = SearchOrchestratorService()
        response = orchestrator.process_agentic_search_request(search_request, g.request_id)
        
        return jsonify(response)
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in agentic search endpoint: {e}")
        raise e  # Will be handled by the error handler