"""FastAPI Search API routes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from ...metrics import get_metrics_collector
from ...server_logging import get_logger
from ..models.requests import (
    AgenticSearchRequest,
    SingleSearchRequest,
)
from ..models.responses import SingleSearchResponse
from ..services.search_orchestrator import SearchOrchestratorService

search_router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()
executor = ThreadPoolExecutor(max_workers=10)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@search_router.post("/single", response_model=SingleSearchResponse)
async def single_search_endpoint(
    single_request: SingleSearchRequest, request_id: str = Depends(get_request_id)
) -> SingleSearchResponse:
    try:
        logger.info(f"[{request_id}] Processing single search")

        loop = asyncio.get_event_loop()
        orchestrator = SearchOrchestratorService()
        result = await loop.run_in_executor(
            executor, orchestrator.process_single_search_request, single_request, request_id
        )

        logger.info(f"[{request_id}] Single search completed successfully")
        return result

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Single search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@search_router.post("/agentic")
async def agentic_search_endpoint(
    agentic_request: AgenticSearchRequest, request_id: str = Depends(get_request_id)
) -> dict[str, Any]:
    try:
        logger.info(f"[{request_id}] Processing agentic search")

        loop = asyncio.get_event_loop()
        orchestrator = SearchOrchestratorService()
        result = await loop.run_in_executor(
            executor, orchestrator.process_agentic_search_request, agentic_request, request_id
        )

        logger.info(f"[{request_id}] Agentic search completed successfully")
        return result

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Agentic search error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
