"""Search-related data models."""

from pydantic import BaseModel, Field


class WebContent(BaseModel):
    """Model for web content data."""
    
    url: str = Field(..., description="Web page URL")
    abstract: str = Field(..., description="Search result abstract/snippet")
    content: str = Field(..., description="Extracted web page content")
    fetch_success: bool = Field(..., description="Whether content fetch was successful")
    is_truncated: bool = Field(default=False, description="Whether content was truncated")


class SearchResult(BaseModel):
    """Model for individual search result."""
    
    url: str = Field(..., description="Result URL")
    abstract: str = Field(..., description="Result abstract/snippet")
    content: str | None = Field(default=None, description="Web page content if fetched")
    fetch_success: bool | None = Field(default=None, description="Content fetch status")
    is_truncated: bool | None = Field(default=None, description="Whether content was truncated")
