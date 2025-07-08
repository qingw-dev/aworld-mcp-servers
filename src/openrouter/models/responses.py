"""Response models for the OpenRouter API."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


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


class ChatCompletionResponse(BaseResponse):
    """Response model for chat completions endpoint."""
    
    response: dict[str, Any] = Field(..., description="OpenRouter API response")
    model: str = Field(..., description="Model used for completion")
    usage: dict[str, Any] | None = Field(default=None, description="Token usage information")
    

class ModelsResponse(BaseResponse):
    """Response model for models endpoint."""
    
    models: dict[str, Any] = Field(..., description="Available models data")
    count: int = Field(..., description="Number of available models")


# Alias for backward compatibility
OpenRouterResponse = ChatCompletionResponse