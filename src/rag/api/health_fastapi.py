"""FastAPI Health check API routes."""

from datetime import datetime

from fastapi import APIRouter

from ...metrics import get_metrics_collector
from ..models.responses import HealthResponse

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health_check():
    """Health check endpoint with system metrics.

    Returns:
        JSON response with service health status and metrics
    """
    metrics_collector = get_metrics_collector()
    current_metrics = metrics_collector.get_metrics()

    response = HealthResponse(
        status="healthy", service="search-server", timestamp=datetime.now(), metrics=current_metrics
    )

    return response.model_dump()
