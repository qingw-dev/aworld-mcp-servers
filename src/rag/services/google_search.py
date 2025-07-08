"""Google Custom Search API service."""

import json
import time

import requests

from ...config import get_settings
from ...server_logging import get_logger
from ...metrics import get_metrics_collector
from ..models.search import SearchResult


class GoogleSearchService:
    """Service for performing Google Custom Search API requests."""
    
    def __init__(self) -> None:
        """Initialize the Google Search service."""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.service_url = "https://www.googleapis.com/customsearch/v1"
    
    def search(
        self,
        query: str,
        api_key: str,
        cse_id: str,
        num_results: int = 5,
        safe_search: bool = True,
        language: str = "en",
        country: str = "US",
        request_id: str | None = None,
    ) -> tuple[list[SearchResult], bool]:
        """Perform a Google Custom Search.
        
        Args:
            query: The search query string
            api_key: Google API key
            cse_id: Google Custom Search Engine ID
            num_results: Number of search results to return
            safe_search: Whether to enable safe search
            language: Search language code
            country: Search country code
            request_id: Request ID for logging
            
        Returns:
            Tuple of (search results list, success status)
        """
        if not api_key or not cse_id:
            self.logger.error(f"[{request_id}] API key or CSE ID not provided for query: {query}")
            self.metrics.increment("failed_searches")
            return [], False
        
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": num_results,
            "safe": "active" if safe_search else "off",
            "hl": language,
            "gl": country,
        }
        
        search_start = time.time()
        self.metrics.increment("total_searches")
        
        try:
            self.logger.info(f"[{request_id}] Executing Google search for query: '{query}'")
            response = requests.get(
                self.service_url, 
                params=params, 
                timeout=self.settings.request_timeout
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            if "items" in data:
                for item in data["items"]:
                    results.append(SearchResult(
                        url=item.get("link", ""),
                        abstract=item.get("snippet", "")
                    ))
            
            search_time = time.time() - search_start
            self.logger.info(
                f"[{request_id}] Google search completed for '{query}' - "
                f"Found {len(results)} results in {search_time:.3f}s"
            )
            self.metrics.increment("successful_searches")
            return results, True
            
        except requests.exceptions.RequestException as e:
            search_time = time.time() - search_start
            self.logger.error(
                f"[{request_id}] Request error during Google search for '{query}': {e} - "
                f"Time: {search_time:.3f}s"
            )
            self.metrics.increment("failed_searches")
            return [], False
            
        except json.JSONDecodeError as e:
            search_time = time.time() - search_start
            self.logger.error(
                f"[{request_id}] JSON decode error for '{query}': {e} - Time: {search_time:.3f}s"
            )
            self.metrics.increment("failed_searches")
            return [], False
            
        except Exception as e:
            search_time = time.time() - search_start
            self.logger.error(
                f"[{request_id}] Unexpected error during Google search for '{query}': {e} - "
                f"Time: {search_time:.3f}s"
            )
            self.metrics.increment("failed_searches")
            return [], False