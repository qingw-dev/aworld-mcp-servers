"""FastAPI Search API routes."""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ...server_logging import get_logger
from ...metrics import get_metrics_collector
from ..models.requests import (
    SearchRequest,
    SingleSearchRequest,
    BatchSearchRequest,
    AgenticSearchRequest,
)
from ..models.responses import ErrorResponse
from ..services.search_orchestrator import SearchOrchestratorService

search_router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()
executor = ThreadPoolExecutor(max_workers=10)


def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, 'request_id', 'unknown')


@search_router.post("/")
async def search_endpoint(
    search_request: SearchRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Main search endpoint for multi-query searches."""
    try:
        logger.info(f"[{request_id}] Processing search request with {len(search_request.queries)} queries")
        
        # Run synchronous search in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            SearchOrchestratorService.search_multi_query,
            search_request
        )
        
        logger.info(f"[{request_id}] Search completed successfully")
        return result
        
    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@search_router.post("/batch")
async def batch_search_endpoint(
    batch_request: BatchSearchRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Batch search endpoint for multiple queries with different credentials."""
    try:
        logger.info(f"[{request_id}] Processing batch search with {len(batch_request.searches)} items")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            SearchOrchestratorService.search_batch,
            batch_request
        )
        
        logger.info(f"[{request_id}] Batch search completed successfully")
        return result
        
    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Batch search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@search_router.post("/agentic")
async def agentic_search_endpoint(
    agentic_request: AgenticSearchRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Agentic search endpoint using the existing search handler."""
    try:
        logger.info(f"[{request_id}] Processing agentic search")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            SearchOrchestratorService.search_agentic,
            agentic_request
        )
        
        logger.info(f"[{request_id}] Agentic search completed successfully")
        return result
        
    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Agentic search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")