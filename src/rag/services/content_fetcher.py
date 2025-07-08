"""Web content fetching service."""

import time

import requests
from bs4 import BeautifulSoup

from ...config import get_settings
from ...logging import get_logger
from ...metrics import get_metrics_collector


class ContentFetcherService:
    """Service for fetching and processing web content."""
    
    def __init__(self) -> None:
        """Initialize the content fetcher service."""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SearchBot/1.0)"
        }
    
    def fetch_content(
        self,
        url: str,
        max_len: int | None = None,
        request_id: str | None = None,
    ) -> tuple[str, bool, bool]:
        """Fetch and extract readable text content from a URL.
        
        Args:
            url: The URL of the web page
            max_len: Maximum length of content to return
            request_id: Request ID for logging
            
        Returns:
            Tuple of (content, fetch_success, is_truncated)
        """
        fetch_start = time.time()
        self.metrics.increment("total_content_fetches")
        
        try:
            self.logger.info(f"[{request_id}] Fetching content from: {url}")
            response = requests.get(
                url,
                timeout=self.settings.request_timeout,
                headers=self.headers
            )
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Remove script and style elements
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            
            # Extract text
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            # Handle truncation
            is_truncated = max_len is not None and len(text) > max_len
            if is_truncated:
                text = text[:max_len]
            
            fetch_time = time.time() - fetch_start
            content_length = len(text)
            truncation_info = " (truncated)" if is_truncated else ""
            
            self.logger.info(
                f"[{request_id}] Successfully fetched content from {url} - "
                f"Length: {content_length} chars{truncation_info} - Time: {fetch_time:.3f}s"
            )
            self.metrics.increment("successful_content_fetches")
            
            return text, True, is_truncated
            
        except requests.exceptions.RequestException as e:
            fetch_time = time.time() - fetch_start
            self.logger.error(
                f"[{request_id}] Request error while fetching content from {url}: {e} - "
                f"Time: {fetch_time:.3f}s"
            )
            self.metrics.increment("failed_content_fetches")
            return "", False, False
            
        except Exception as e:
            fetch_time = time.time() - fetch_start
            self.logger.error(
                f"[{request_id}] Unexpected error while parsing content from {url}: {e} - "
                f"Time: {fetch_time:.3f}s"
            )
            self.metrics.increment("failed_content_fetches")
            return "", False, False