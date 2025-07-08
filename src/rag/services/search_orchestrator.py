"""Search orchestrator service that coordinates search operations."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...config import get_settings
from ...logging import get_logger
from ..models.requests import (
    SearchRequest,
    SingleSearchRequest,
    BatchSearchRequest,
    AgenticSearchRequest,
)
from ..models.responses import (
    SearchResponse,
    SingleSearchResponse,
    BatchSearchResponse,
)
from ..models.search import SearchResult
from .google_search import GoogleSearchService
from .content_fetcher import ContentFetcherService
from .search_handler import handle_single_query, AuthArgs


class SearchOrchestratorService:
    """Service that orchestrates search operations across different components."""
    
    def __init__(self) -> None:
        """Initialize the search orchestrator service."""
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.google_search = GoogleSearchService()
        self.content_fetcher = ContentFetcherService()
    
    def process_search_request(
        self, 
        request: SearchRequest, 
        request_id: str
    ) -> SearchResponse:
        """Process a multi-query search request.
        
        Args:
            request: The search request
            request_id: Unique request identifier
            
        Returns:
            Search response with results
        """
        self.logger.info(
            f"[{request_id}] Processing search request - "
            f"Queries: {len(request.queries)}, Results per query: {request.num_results}"
        )
        
        results = self._process_queries_concurrent(
            queries=request.queries,
            api_key=request.api_key,
            cse_id=request.cse_id,
            num_results=request.num_results,
            language=request.language,
            country=request.country,
            safe_search=request.safe_search,
            max_len=request.max_len,
            request_id=request_id,
        )
        
        return SearchResponse(
            success=True,
            request_id=request_id,
            results=results,
            query_count=len(request.queries),
            parameters={
                "num_results": request.num_results,
                "language": request.language,
                "country": request.country,
                "safe_search": request.safe_search,
                "max_len": request.max_len,
            },
        )
    
    def process_single_search_request(
        self, 
        request: SingleSearchRequest, 
        request_id: str
    ) -> SingleSearchResponse:
        """Process a single query search request.
        
        Args:
            request: The single search request
            request_id: Unique request identifier
            
        Returns:
            Single search response with results
        """
        self.logger.info(
            f"[{request_id}] Processing single search request - "
            f"Query: '{request.query}', Fetch content: {request.fetch_content}"
        )
        
        # Perform Google search
        search_results, search_success = self.google_search.search(
            query=request.query,
            api_key=request.api_key,
            cse_id=request.cse_id,
            num_results=request.num_results,
            safe_search=request.safe_search,
            language=request.language,
            country=request.country,
            request_id=request_id,
        )
        
        if not search_success:
            self.logger.error(f"[{request_id}] Search failed for query: '{request.query}'")
            return SingleSearchResponse(
                success=False,
                request_id=request_id,
                query=request.query,
                results=[],
                count=0,
            )
        
        # Fetch content if requested
        if request.fetch_content and search_results:
            enhanced_results = self._fetch_content_for_results(
                search_results, request.max_len, request_id
            )
        else:
            enhanced_results = search_results
        
        return SingleSearchResponse(
            success=True,
            request_id=request_id,
            query=request.query,
            results=enhanced_results,
            count=len(enhanced_results),
        )
    
    def process_batch_search_request(
        self, 
        request: BatchSearchRequest, 
        request_id: str
    ) -> BatchSearchResponse:
        """Process a batch search request.
        
        Args:
            request: The batch search request
            request_id: Unique request identifier
            
        Returns:
            Batch search response with results
        """
        self.logger.info(
            f"[{request_id}] Processing batch search request - "
            f"Searches: {len(request.searches)}, Fetch content: {request.fetch_content}"
        )
        
        def process_batch_search_item(search_item, index: int):
            """Process a single batch search item."""
            try:
                # Perform search
                search_results, search_success = self.google_search.search(
                    query=search_item.query,
                    api_key=search_item.api_key,
                    cse_id=search_item.cse_id,
                    num_results=search_item.num_results,
                    safe_search=search_item.safe_search,
                    language=search_item.language,
                    country=search_item.country,
                    request_id=f"{request_id}-{index}",
                )
                
                if not search_success:
                    return {
                        "query": search_item.query,
                        "success": False,
                        "results": [],
                        "error": "Search failed"
                    }
                
                # Fetch content if requested
                if request.fetch_content and search_results:
                    enhanced_results = self._fetch_content_for_results(
                        search_results, search_item.max_len, f"{request_id}-{index}"
                    )
                else:
                    enhanced_results = search_results
                
                return {
                    "query": search_item.query,
                    "success": True,
                    "results": [result.dict() for result in enhanced_results],
                    "count": len(enhanced_results)
                }
                
            except Exception as e:
                self.logger.error(f"[{request_id}-{index}] Error processing batch item: {e}")
                return {
                    "query": search_item.query,
                    "success": False,
                    "results": [],
                    "error": str(e)
                }
        
        # Process batch searches concurrently
        results = []
        successful_searches = 0
        
        with ThreadPoolExecutor(max_workers=min(self.settings.max_workers, len(request.searches))) as executor:
            future_to_index = {
                executor.submit(process_batch_search_item, search_item, index): index
                for index, search_item in enumerate(request.searches)
            }
            
            for future in as_completed(future_to_index):
                try:
                    result = future.result()
                    results.append(result)
                    if result["success"]:
                        successful_searches += 1
                except Exception as e:
                    index = future_to_index[future]
                    self.logger.error(f"[{request_id}] Error in batch search {index}: {e}")
                    results.append({
                        "query": request.searches[index].query,
                        "success": False,
                        "results": [],
                        "error": "Processing error"
                    })
        
        return BatchSearchResponse(
            success=True,
            request_id=request_id,
            results=results,
            total_searches=len(request.searches),
            successful_searches=successful_searches,
        )
    
    def process_agentic_search_request(
        self, 
        request: AgenticSearchRequest, 
        request_id: str
    ) -> dict:
        """Process an agentic search request using the existing handler.
        
        Args:
            request: The agentic search request
            request_id: Unique request identifier
            
        Returns:
            Agentic search results
        """
        self.logger.info(
            f"[{request_id}] Processing agentic search request - "
            f"Question: '{request.question}', Queries: {len(request.search_queries)}"
        )
        
        try:
            auth_args = AuthArgs(
                base_url=request.base_url,
                api_key=request.api_key,
                serper_api_key=request.serper_api_key,
                llm_model_name=request.llm_model_name,
            )
            
            search_results = handle_single_query(
                question=request.question,
                search_query_list=request.search_queries,
                auth_args=auth_args,
                topk=request.topk,
            )
            
            if search_results:
                return {
                    "success": True,
                    "request_id": request_id,
                    "question": request.question,
                    "search_queries": request.search_queries,
                    "results": search_results.dict() if hasattr(search_results, 'dict') else search_results,
                }
            else:
                return {
                    "success": False,
                    "request_id": request_id,
                    "error": "No results found",
                }
                
        except Exception as e:
            self.logger.error(f"[{request_id}] Error in agentic search: {e}")
            return {
                "success": False,
                "request_id": request_id,
                "error": str(e),
            }
    
    def _process_queries_concurrent(
        self,
        queries: list[str],
        api_key: str,
        cse_id: str,
        num_results: int,
        language: str,
        country: str,
        safe_search: bool,
        max_len: int | None,
        request_id: str,
    ) -> dict[str, list[SearchResult]]:
        """Process multiple queries concurrently.
        
        Args:
            queries: List of search queries
            api_key: Google API key
            cse_id: Google CSE ID
            num_results: Number of results per query
            language: Search language
            country: Search country
            safe_search: Safe search setting
            max_len: Maximum content length
            request_id: Request ID for logging
            
        Returns:
            Dictionary mapping queries to their results
        """
        process_start = time.time()
        output_data = {}
        
        def process_single_query(query: str) -> tuple[str, list[SearchResult]]:
            """Process a single query with content fetching."""
            query_start = time.time()
            
            # Perform Google search
            search_results, search_success = self.google_search.search(
                query=query,
                api_key=api_key,
                cse_id=cse_id,
                num_results=num_results,
                safe_search=safe_search,
                language=language,
                country=country,
                request_id=request_id,
            )
            
            if not search_success or not search_results:
                self.logger.warning(f"[{request_id}] No search results for query: {query}")
                return query, []
            
            # Fetch content for all results
            enhanced_results = self._fetch_content_for_results(
                search_results, max_len, request_id
            )
            
            query_time = time.time() - query_start
            self.logger.info(
                f"[{request_id}] Completed processing query: {query} - "
                f"Results: {len(enhanced_results)} - Time: {query_time:.3f}s"
            )
            
            return query, enhanced_results
        
        # Process queries concurrently
        with ThreadPoolExecutor(max_workers=min(self.settings.max_workers, len(queries))) as executor:
            future_to_query = {
                executor.submit(process_single_query, query): query
                for query in queries
            }
            
            for future in as_completed(future_to_query):
                try:
                    query, results = future.result()
                    output_data[query] = results
                except Exception as e:
                    query = future_to_query[future]
                    self.logger.error(f"[{request_id}] Error processing query '{query}': {e}")
                    output_data[query] = []
        
        process_time = time.time() - process_start
        successful_queries = sum(1 for results in output_data.values() if results)
        
        self.logger.info(
            f"[{request_id}] Completed concurrent processing - "
            f"Total queries: {len(queries)}, Successful: {successful_queries}, Time: {process_time:.3f}s"
        )
        
        return output_data
    
    def _fetch_content_for_results(
        self, 
        search_results: list[SearchResult], 
        max_len: int | None, 
        request_id: str
    ) -> list[SearchResult]:
        """Fetch content for a list of search results.
        
        Args:
            search_results: List of search results
            max_len: Maximum content length
            request_id: Request ID for logging
            
        Returns:
            List of search results with content
        """
        def fetch_single_result(result: SearchResult) -> SearchResult:
            """Fetch content for a single search result."""
            if result.url:
                content, fetch_success, is_truncated = self.content_fetcher.fetch_content(
                    url=result.url,
                    max_len=max_len,
                    request_id=request_id,
                )
                
                # Update the result with content information
                result.content = content
                result.fetch_success = fetch_success
                result.is_truncated = is_truncated
            else:
                self.logger.warning(f"[{request_id}] Skipping result with no URL")
                result.content = ""
                result.fetch_success = False
                result.is_truncated = False
            
            return result
        
        # Fetch content concurrently
        enhanced_results = []
        with ThreadPoolExecutor(max_workers=min(self.settings.max_content_workers, len(search_results))) as executor:
            future_to_result = {
                executor.submit(fetch_single_result, result): result 
                for result in search_results
            }
            
            for future in as_completed(future_to_result):
                try:
                    result = future.result()
                    enhanced_results.append(result)
                except Exception as e:
                    self.logger.error(f"[{request_id}] Error fetching content for result: {e}")
                    # Add the original result without content
                    original_result = future_to_result[future]
                    original_result.content = ""
                    original_result.fetch_success = False
                    original_result.is_truncated = False
                    enhanced_results.append(original_result)
        
        return enhanced_results