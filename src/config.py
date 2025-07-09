"""Configuration management using Pydantic settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=19090, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # Search settings
    num_results: int = Field(default=5, description="Default number of search results")
    max_workers: int = Field(default=10, description="Maximum concurrent workers")
    max_content_workers: int = Field(default=5, description="Maximum content fetch workers")
    request_timeout: int = Field(default=15, description="Request timeout in seconds")

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="search_server.log", description="Log file path")

    # Optional API keys (can be provided per request)
    google_api_key: str | None = Field(default=None, description="Default Google API key")
    google_cse_id: str | None = Field(default=None, description="Default Google CSE ID")

    class Config:
        env_file = ".env"
        env_prefix = "SEARCH_"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
