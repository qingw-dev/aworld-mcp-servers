"""Health check API routes."""

from datetime import datetime
from flask import Blueprint, jsonify

from ..core.metrics import get_metrics_collector
from ..models.responses import HealthResponse

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint with system metrics.
    
    Returns:
        JSON response with service health status and metrics
    """
    metrics_collector = get_metrics_collector()
    current_metrics = metrics_collector.get_metrics()
    
    response = HealthResponse(
        status="healthy",
        service="search-server",
        timestamp=datetime.now(),
        metrics=current_metrics
    )
    
    return jsonify(response.model_dump())