"""Request models for the OpenRouter API."""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class BaseOpenRouterRequest(BaseModel):
    """Base OpenRouter request with common fields."""
    
    api_key: str = Field(..., description="OpenRouter API key", min_length=1)
    site_url: str | None = Field(default=None, description="Site URL for HTTP-Referer header")
    site_name: str | None = Field(default=None, description="Site name for X-Title header")
    
    @field_validator('api_key')
    def validate_api_key(cls, v: str) -> str:
        """Ensure API key is not empty."""
        if not v.strip():
            raise ValueError("API key cannot be empty")
        return v.strip()


class ChatCompletionRequest(BaseOpenRouterRequest):
    """Request model for chat completions endpoint."""
    
    model: str = Field(default="google/gemini-2.5-pro", description="Model to use for completion")
    messages: list[dict[str, Any]] = Field(..., description="List of messages", min_items=1)
    max_tokens: int | None = Field(default=None, description="Maximum tokens to generate", ge=1)
    temperature: float | None = Field(default=None, description="Sampling temperature", ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, description="Nucleus sampling parameter", ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, description="Frequency penalty", ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, description="Presence penalty", ge=-2.0, le=2.0)
    stream: bool = Field(default=False, description="Whether to stream responses")
    
    @field_validator('messages')
    def validate_messages(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure messages list is not empty and has valid structure."""
        if not v:
            raise ValueError("Messages list cannot be empty")
        
        for i, message in enumerate(v):
            if not isinstance(message, dict):
                raise ValueError(f"Message {i} must be a dictionary")
            if 'role' not in message or 'content' not in message:
                raise ValueError(f"Message {i} must have 'role' and 'content' fields")
        
        return v


# Alias for backward compatibility
OpenRouterRequest = ChatCompletionRequest