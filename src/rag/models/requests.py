"""Request models for the search API."""

from pydantic import BaseModel, Field, field_validator


class BaseSearchRequest(BaseModel):
    """Base search request with common fields."""
    
    api_key: str = Field(..., description="Google API key", min_length=1)
    cse_id: str = Field(..., description="Google Custom Search Engine ID", min_length=1)
    num_results: int = Field(default=5, description="Number of results to return", ge=1, le=10)
    language: str = Field(default="en", description="Search language code")
    country: str = Field(default="US", description="Search country code")
    safe_search: bool = Field(default=True, description="Enable safe search")
    max_len: int | None = Field(default=None, description="Maximum content length", ge=1)
    
    @field_validator('api_key', 'cse_id')
    def validate_not_empty(cls, v: str) -> str:
        """Ensure API key and CSE ID are not empty strings."""
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class SearchRequest(BaseSearchRequest):
    """Request model for multi-query search endpoint."""
    
    queries: list[str] = Field(..., description="List of search queries", min_items=1)
    
    @field_validator('queries')
    def validate_queries(cls, v: list[str]) -> list[str]:
        """Ensure all queries are non-empty strings."""
        if not v:
            raise ValueError("Queries list cannot be empty")
        return [q.strip() for q in v if q.strip()]


class SingleSearchRequest(BaseSearchRequest):
    """Request model for single query search endpoint."""
    
    query: str = Field(..., description="Search query", min_length=1)
    fetch_content: bool = Field(default=True, description="Whether to fetch web content")
    
    @field_validator('query')
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class BatchSearchItem(BaseSearchRequest):
    """Individual search item for batch requests."""
    
    query: str = Field(..., description="Search query", min_length=1)
    
    @field_validator('query')
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class BatchSearchRequest(BaseModel):
    """Request model for batch search endpoint."""
    
    searches: list[BatchSearchItem] = Field(..., description="List of search items", min_items=1)
    fetch_content: bool = Field(default=True, description="Whether to fetch web content")


class AgenticSearchRequest(BaseModel):
    """Request model for agentic search endpoint."""
    
    question: str = Field(..., description="User question", min_length=1)
    search_queries: list[str] = Field(..., description="Search queries", min_items=1)
    base_url: str = Field(..., description="OpenAI API base URL")
    api_key: str = Field(..., description="OpenAI API key", min_length=1)
    serper_api_key: str = Field(..., description="Serper API key", min_length=1)
    topk: int = Field(default=5, description="Top K results", ge=1, le=20)
    
    @field_validator('question')
    def validate_question(cls, v: str) -> str:
        """Ensure question is not empty."""
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()
    
    @field_validator('search_queries')
    def validate_search_queries(cls, v: list[str]) -> list[str]:
        """Ensure all search queries are non-empty strings."""
        if not v:
            raise ValueError("Search queries list cannot be empty")
        return [q.strip() for q in v if q.strip()]