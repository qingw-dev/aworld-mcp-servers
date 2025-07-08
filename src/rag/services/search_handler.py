"""Legacy search handler service - to be gradually migrated."""

import concurrent.futures
import logging
import os
import traceback
from dataclasses import dataclass
from pathlib import Path

import yaml
from openai import OpenAI
from pydantic import BaseModel, Field

from ..agents.reading_agent import ReadingAgent
from ..agents.web_search_agent import WebSearchAgent, web_search
from ..core.logging import get_logger
from ..models.webpage import PageReadInfo, SearchResultInfo, WebPageInfo

# Load configuration
config = yaml.safe_load(open(Path(__file__).parent.parent / "config.yml"))


@dataclass
class AuthArgs:
    """Authentication arguments for external services."""
    
    base_url: str
    api_key: str
    serper_api_key: str


class WebPageDetail(BaseModel):
    """Detailed webpage information for API responses."""
    
    title: str = Field(..., description="Page title")
    url: str = Field(..., description="Page URL")
    quick_summary: str = Field(..., description="Page summary")
    sub_question: str = Field(..., description="Page sub-question")
    page_read_info_list: list[PageReadInfo] = Field(
        ..., description="Page reading information"
    )


class SearchResult(BaseModel):
    """Individual search result with optional detailed information."""
    
    user_question: str = Field(..., description="User's original question")
    search_query: str = Field(..., description="Search query used")
    search_result_info_list: list[SearchResultInfo] = Field(
        ..., description="Search result information"
    )
    search_detail: dict[str, WebPageDetail] | None = Field(
        default=None, description="Detailed search information"
    )


class SearchResults(BaseModel):
    """Collection of search results."""
    
    search_results: list[SearchResult] = Field(
        ..., description="List of search results"
    )


def convert_web_page_info_to_detail(web_page_info: WebPageInfo) -> WebPageDetail:
    """Convert WebPageInfo to WebPageDetail for API responses.
    
    Args:
        web_page_info: Source webpage information
        
    Returns:
        Converted webpage detail
    """
    return WebPageDetail(
        title=web_page_info.title,
        url=web_page_info.url,
        quick_summary=web_page_info.quick_summary,
        sub_question=web_page_info.sub_question,
        page_read_info_list=web_page_info.page_read_info_list,
    )


def web_search_batch(search_query_list: list[str], serper_api_key: str) -> dict:
    """Perform batch web searches concurrently.
    
    Args:
        search_query_list: List of search queries
        serper_api_key: API key for search service
        
    Returns:
        Dictionary mapping queries to search results
    """
    logger = get_logger(__name__)
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_content = [
                executor.submit(web_search, search_query, config, serper_api_key)
                for search_query in search_query_list
            ]
        
        results = {}
        for query, future in zip(search_query_list, future_to_content):
            try:
                results[query] = {"organic": future.result()}
            except Exception as e:
                logger.error(f"Error in search for query '{query}': {e}")
                results[query] = {"organic": []}
        
        return results
        
    except Exception as e:
        logger.error(f"web_search_batch error: {e}")
        return {}


def handle_single_query(
    question: str,
    search_query_list: list[str],
    auth_args: AuthArgs,
    topk: int = 5,
) -> SearchResults | None:
    """Handle a single research query with multiple search terms.
    
    This function orchestrates the complete research pipeline:
    1. Perform web searches for all queries
    2. Extract and analyze search results
    3. Read and extract information from selected pages
    4. Return structured results
    
    Args:
        question: Main research question
        search_query_list: List of search queries to execute
        auth_args: Authentication arguments
        topk: Maximum number of queries to process
        
    Returns:
        Structured search results or None if failed
    """
    logger = get_logger(__name__)
    
    # Initialize clients and agents
    client = OpenAI(base_url=auth_args.base_url, api_key=auth_args.api_key)
    web_search_agent = WebSearchAgent(
        client=client, config=config, serper_api_key=auth_args.serper_api_key
    )
    reading_agent = ReadingAgent(client=client, config=config)
    
    try:
        # Limit number of queries
        search_query_list = search_query_list[:topk] if len(search_query_list) > topk else search_query_list
        
        # Perform batch web searches
        api_result_dict = web_search_batch(search_query_list, auth_args.serper_api_key)
        
        # Process search results
        web_page_info_list_batch = web_search_agent.search_web_batch(
            user_query=question,
            search_query_list=search_query_list,
            api_result_dict=api_result_dict,
        )
        
        # Build search result info list
        search_result_info_list: list[SearchResultInfo] = []
        for search_query, web_page_info_list in zip(search_query_list, web_page_info_list_batch):
            data = {
                "search_query": search_query,
                "web_page_info_list": [info.model_dump() for info in web_page_info_list],
                "web_select_info_list": [],
            }
            search_result_info = SearchResultInfo.model_validate(data)
            search_result_info_list.append(search_result_info)
        
        # Create initial search results
        search_results: list[SearchResult] = []
        for search_result_info in search_result_info_list:
            search_results.append(
                SearchResult(
                    user_question=question,
                    search_query=search_result_info.search_query,
                    search_result_info_list=search_result_info_list,
                    search_detail=None,
                )
            )
        
    except Exception as e:
        logger.error(f"handle_single_query error: {traceback.format_exc()}")
        return None
    
    try:
        # Read and extract detailed information
        for search_result in search_results:
            urls: list[str] = []
            for search_info in search_result.search_result_info_list:
                for web_page_info in search_info.web_page_info_list:
                    urls.append(web_page_info.url)
            
            # Read webpages in batch
            read_webpage_list: list[WebPageInfo] = reading_agent.read_batch(
                user_query=question,
                search_result_info_list=search_result.search_result_info_list,
                url_list=urls,
                web_search_agent=web_search_agent,
            )
            
            # Convert to detailed format
            web_detail_dict: dict[str, WebPageDetail] = {
                read_webpage.url: convert_web_page_info_to_detail(read_webpage)
                for read_webpage in read_webpage_list
            }
            search_result.search_detail = web_detail_dict
        
        return SearchResults(search_results=search_results)
        
    except Exception as e:
        logger.error(f"handle_single_query reading error: {traceback.format_exc()}")
        return None


def check_health() -> None:
    """Perform health check of the search pipeline.
    
    Raises:
        AssertionError: If health check fails
    """
    logger = get_logger(__name__)
    
    auth_args = AuthArgs(
        base_url=os.getenv("base_url", ""),
        api_key=os.getenv("api_key", ""),
        serper_api_key=os.getenv("serper_api_key", ""),
    )
    
    search_results = handle_single_query(
        "machine learning", ["machine learning"], auth_args
    )
    
    assert search_results and len(search_results.search_results) > 0, "search_results is empty"
    logger.info("DeepResearcher pipeline [search+browse+read+summary] is healthy!")


if __name__ == "__main__":
    check_health()