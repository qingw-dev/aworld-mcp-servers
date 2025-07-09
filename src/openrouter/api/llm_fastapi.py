"""FastAPI OpenRouter LLM API routes."""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import ValidationError
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ...server_logging import get_logger
from ...metrics import get_metrics_collector
from ..models.requests import ChatCompletionRequest
from ..models.responses import ErrorResponse
from ..services.openrouter_service import OpenRouterService

openrouter_router = APIRouter(prefix="/openrouter", tags=["openrouter"])
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()
executor = ThreadPoolExecutor(max_workers=5)


def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, 'request_id', 'unknown')


@openrouter_router.post("/completions")
async def chat_completions(
    chat_request: ChatCompletionRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
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
    try:
        logger.info(f"[{request_id}] Processing chat completion request")
        
        # Process request in thread pool
        service = OpenRouterService()
        loop = asyncio.get_event_loop()
        response, success = await loop.run_in_executor(
            executor,
            service.chat_completion,
            chat_request,
            request_id
        )
        
        if not success:
            logger.error(f"[{request_id}] OpenRouter API request failed")
            raise HTTPException(
                status_code=502,
                detail="OpenRouter API request failed"
            )
        
        logger.info(f"[{request_id}] Chat completion completed successfully")
        return response.model_dump()
        
    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in chat completions endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@openrouter_router.get("/models")
async def list_models(
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """List available models endpoint."""
    try:
        logger.info(f"[{request_id}] Fetching available models")
        
        # Process request in thread pool
        service = OpenRouterService()
        loop = asyncio.get_event_loop()
        response, success = await loop.run_in_executor(
            executor,
            service.list_models,
            request_id
        )
        
        if not success:
            logger.error(f"[{request_id}] Failed to fetch models")
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch models from OpenRouter API"
            )
        
        logger.info(f"[{request_id}] Models fetched successfully")
        return response.model_dump()
        
    except Exception as e:
        logger.error(f"[{request_id}] Error in models endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")