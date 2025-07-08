"""Response models for the search API."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from .search import SearchResult
from ...metrics import SearchMetrics


class BaseResponse(BaseModel):
    """Base response model with common fields."""
    
    success: bool = Field(..., description="Whether the request was successful")
    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class ErrorResponse(BaseResponse):
    """Error response model."""
    
    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    details: str | None = Field(default=None, description="Additional error details")


class SearchResponse(BaseResponse):
    """Response model for multi-query search endpoint."""
    
    results: dict[str, list[SearchResult]] = Field(..., description="Search results by query")
    query_count: int = Field(..., description="Number of queries processed")
    parameters: dict[str, Any] = Field(..., description="Request parameters used")


class SingleSearchResponse(BaseResponse):
    """Response model for single query search endpoint."""
    
    query: str = Field(..., description="The search query")
    results: list[SearchResult] = Field(..., description="Search results")
    count: int = Field(..., description="Number of results returned")


class BatchSearchResponse(BaseResponse):
    """Response model for batch search endpoint."""
    
    results: list[dict[str, Any]] = Field(..., description="Batch search results")
    total_searches: int = Field(..., description="Total number of searches processed")
    successful_searches: int = Field(..., description="Number of successful searches")


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")
    metrics: SearchMetrics = Field(..., description="Service metrics")