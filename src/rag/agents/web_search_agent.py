"""Enhanced web search agent with improved error handling and modern Python features."""

import concurrent.futures
import json
import os
import threading
from typing import Any

import requests
from openai import OpenAI

from ..browser.text_web_browser import SimpleTextBrowser
from ...server_logging import get_logger
from ..models.webpage import WebPageInfo

logger = get_logger(__name__)


def web_search(
    query: str, 
    config: dict[str, Any], 
    serper_api_key: str
) -> list[dict[str, Any]]:
    """Perform web search using Serper API.
    
    Args:
        query: Search query string
        config: Configuration dictionary
        serper_api_key: Serper API key
        
    Returns:
        List of search results
        
    Raises:
        ValueError: If query is empty
        NotImplementedError: If search engine is not supported
    """
    if not query:
        raise ValueError("Search query cannot be empty")
        
    if config["search_engine"] == "google":
        return _serper_google_search(
            query=query,
            serper_api_key=serper_api_key,
            top_k=config["search_top_k"],
            region=config["search_region"],
            lang=config["search_lang"],
        )
    else:
        raise NotImplementedError(f"Search engine '{config['search_engine']}' not supported")


def _serper_google_search(
    query: str, 
    serper_api_key: str, 
    top_k: int, 
    region: str, 
    lang: str
) -> list[dict[str, Any]]:
    """Perform Google search using Serper API.
    
    Args:
        query: Search query
        serper_api_key: Serper API key
        top_k: Number of results to return
        region: Search region
        lang: Search language
        
    Returns:
        List of search results
    """
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": serper_api_key,
            "Content-Type": "application/json"
        }
        payload = json.dumps({
            "q": query,
            "num": top_k,
            "gl": region,
            "hl": lang,
        })
        
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            raise Exception("Google search API returned empty response")
            
        if "organic" not in data:
            raise Exception(f"No results found for query: '{query}'. Try a different query.")
            
        logger.info(f"Search successful for query: '{query}'")
        return data["organic"]
        
    except requests.RequestException as e:
        logger.error(f"Serper search API request error: {e}")
        return []
    except Exception as e:
        logger.error(f"Serper search API error: {e}")
        return []


class WebSearchAgent:
    """Agent responsible for web searching and content extraction.
    
    This agent handles:
    1. Web search operations using various search engines
    2. Content fetching and validation
    3. Browser management and caching
    4. Concurrent processing of multiple searches
    """

    def __init__(
        self, 
        client: OpenAI, 
        config: dict[str, Any], 
        serper_api_key: str
    ) -> None:
        """Initialize the web search agent.
        
        Args:
            client: OpenAI client instance
            config: Configuration dictionary
            serper_api_key: Serper API key
        """
        self.client = client
        self.config = config
        self.serper_api_key = serper_api_key
        self.logger = get_logger(self.__class__.__name__)
        
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
        )

        self.browser_config = {
            "viewport_size": 1024 * 5 * 8,
            "downloads_folder": "downloads_folder",
            "request_kwargs": {
                "headers": {"User-Agent": self.user_agent},
                "timeout": (5, 10),
            },
            "serper_api_key": serper_api_key,
        }
        
        # Ensure downloads folder exists
        downloads_path = f"./{self.browser_config['downloads_folder']}"
        if not os.path.exists(downloads_path):
            self.logger.info(f"Creating downloads directory: {os.path.abspath(downloads_path)}")
            os.makedirs(downloads_path, exist_ok=True)

        # Thread-safe caches
        self.search_history: dict[str, dict[str, Any]] = {}
        self.search_history_lock = threading.Lock()
        self.url_browser_dict: dict[str, SimpleTextBrowser] = {}
        self.url_browser_dict_lock = threading.Lock()

    def save_search_history(self, file_path: str) -> None:
        """Save search history to file.
        
        Args:
            file_path: Path to save the search history
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.search_history, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Search history saved to {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save search history: {e}")

    def scrape_content(
        self, 
        browser: SimpleTextBrowser, 
        url: str
    ) -> str:
        """Scrape content from a webpage.
        
        Args:
            browser: Browser instance
            url: URL to scrape
            
        Returns:
            Scraped content
        """
        try:
            browser.visit_page(url)
            header, content = browser._state()
            return header.strip() + "\n" + "=" * 50 + "\n" + content
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return "## Error: Failed to fetch page content"

    def is_error_page(self, browser: SimpleTextBrowser) -> bool:
        """Check if the current page is an error page.
        
        Args:
            browser: Browser instance to check
            
        Returns:
            True if it's an error page, False otherwise
        """
        if isinstance(browser.page_title, tuple):
            return True
            
        return (
            browser.page_title is not None and
            browser.page_title.startswith("Error ") and
            browser.page_content is not None and
            browser.page_content.startswith("## Error ")
        )

    def fetch_content(
        self, 
        browser: SimpleTextBrowser, 
        url: str
    ) -> str:
        """Fetch content with error handling.
        
        Args:
            browser: Browser instance
            url: URL to fetch
            
        Returns:
            Fetched content or error message
        """
        try:
            return self.scrape_content(browser, url)
        except Exception as e:
            self.logger.error(f"Content fetch failed for {url}: {e}")
            return "## Error: No valid information in this page"

    def scrape_and_check_valid_api(self, url: str) -> SimpleTextBrowser | None:
        """Scrape URL and validate content.
        
        Args:
            url: URL to scrape and validate
            
        Returns:
            Browser instance if valid, None if invalid
        """
        try:
            browser = SimpleTextBrowser(**self.browser_config)
            content = self.fetch_content(browser, url)
            
            if content is None:
                return None
                
            if self.is_error_page(browser):
                self.logger.warning(f"Error page detected, skipping URL: {url}")
                return None
                
            return browser
            
        except Exception as e:
            self.logger.error(f"Failed to scrape and validate {url}: {e}")
            return None

    def search_web(
        self, 
        user_query: str, 
        search_query: str, 
        api_result_dict: dict[str, dict[str, Any]]
    ) -> list[WebPageInfo]:
        """Process search results into WebPageInfo objects.
        
        Args:
            user_query: Original user query
            search_query: Specific search query
            api_result_dict: Search API results
            
        Returns:
            List of WebPageInfo objects
        """
        try:
            organic_results = api_result_dict[search_query]["organic"]
            web_page_info_list = []
            
            for site in organic_results:
                web_page_info = WebPageInfo(
                    title=site.get("title", "No Title"),
                    url=site.get("link", ""),
                    quick_summary=site.get("snippet", ""),
                    browser=None,
                    sub_question=search_query,
                )
                web_page_info_list.append(web_page_info)
                
            return web_page_info_list
            
        except Exception as e:
            self.logger.error(f"Error processing search results for '{search_query}': {e}")
            return []

    def search_web_batch(
        self, 
        user_query: str, 
        search_query_list: list[str], 
        api_result_dict: dict[str, dict[str, Any]],
        max_workers: int = 10
    ) -> list[list[WebPageInfo]]:
        """Process multiple search queries concurrently.
        
        Args:
            user_query: Original user query
            search_query_list: List of search queries
            api_result_dict: Search API results dictionary
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of lists containing WebPageInfo objects
        """
        try:
            web_page_info_list_batch = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_query = {
                    executor.submit(self.search_web, user_query, query, api_result_dict): query
                    for query in search_query_list
                }
                
            for future in concurrent.futures.as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    web_page_info_list = future.result()
                    web_page_info_list_batch.append(web_page_info_list)
                except Exception as e:
                    self.logger.error(f"Error processing batch search for '{query}': {e}")
                    web_page_info_list_batch.append([])
                    
            return web_page_info_list_batch
            
        except Exception as e:
            self.logger.error(f"Batch search processing failed: {e}")
            return []