"""OpenRouter LLM API routes."""

import uuid
from flask import Blueprint, request, jsonify, g
from pydantic import ValidationError

from ...logging import get_logger
from ...metrics import get_metrics_collector
from ..models.requests import ChatCompletionRequest
from ..models.responses import ErrorResponse
from ..services.openrouter_service import OpenRouterService

openrouter_bp = Blueprint("openrouter", __name__, url_prefix="/openrouter")
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


@openrouter_bp.before_request
def add_request_id():
    """Add unique request ID to each OpenRouter request."""
    g.request_id = str(uuid.uuid4())[:8]


@openrouter_bp.errorhandler(ValidationError)
def handle_validation_error(error: ValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(f"[{g.request_id}] Validation error: {error}")
    response = ErrorResponse(
        request_id=g.request_id,
        error="Validation error",
        details=str(error),
    )
    return jsonify(response.model_dump()), 400


@openrouter_bp.errorhandler(Exception)
def handle_general_error(error: Exception):
    """Handle general exceptions."""
    logger.error(f"[{g.request_id}] Unexpected error: {error}")
    response = ErrorResponse(
        request_id=g.request_id,
        error="Internal server error",
        details="An unexpected error occurred",
    )
    return jsonify(response.model_dump()), 500


@openrouter_bp.route("/completions", methods=["POST"])
@metrics_collector.log_performance
def chat_completions():
    """Chat completions endpoint.
    
    Expected JSON payload:
    {
        "model": "google/gemini-2.5-pro",
        "messages": [{"role": "user", "content": "Hello"}],
        "api_key": "your_openrouter_api_key",
        "max_tokens": 1000,  // optional
        "temperature": 0.7,  // optional
        "site_url": "https://example.com",  // optional
        "site_name": "My App"  // optional
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
        chat_request = ChatCompletionRequest(**request.get_json())
        
        # Process request
        service = OpenRouterService()
        response, success = service.chat_completion(chat_request, g.request_id)
        
        if not success:
            error_response = ErrorResponse(
                request_id=g.request_id,
                error="OpenRouter API request failed",
                details="Failed to complete chat request",
            )
            return jsonify(error_response.model_dump()), 502
        
        return jsonify(response.model_dump())
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in chat completions endpoint: {e}")
        raise e  # Will be handled by the error handler


@openrouter_bp.route("/models", methods=["GET"])
@metrics_collector.log_performance
def list_models():
    """List available models endpoint."""
    try:
        # Process request
        service = OpenRouterService()
        response, success = service.list_models(g.request_id)
        
        if not success:
            error_response = ErrorResponse(
                request_id=g.request_id,
                error="Failed to fetch models",
                details="OpenRouter API request failed",
            )
            return jsonify(error_response.model_dump()), 502
        
        return jsonify(response.model_dump())
        
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in models endpoint: {e}")
        raise e  # Will be handled by the error handler