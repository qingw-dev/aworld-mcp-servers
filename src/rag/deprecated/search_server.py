import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig
import subprocess
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

from src.rag.search_handler import AuthArgs, SearchResults, handle_single_query

# --- Configuration ---
# Default number of search results to fetch per query
NUM_RESULTS = 5
# Maximum number of concurrent threads for processing
MAX_WORKERS = 10
# Request timeout in seconds
REQUEST_TIMEOUT = 15
# Maximum content fetch workers per query
MAX_CONTENT_WORKERS = 5

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("search_server.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Thread-safe metrics storage
metrics_lock = threading.Lock()
metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_searches": 0,
    "successful_searches": 0,
    "failed_searches": 0,
    "total_content_fetches": 0,
    "successful_content_fetches": 0,
    "failed_content_fetches": 0,
    "average_response_time": 0.0,
    "response_times": [],
}


def update_metrics(metric_name: str, value: float = 1.0):
    """Thread-safe metrics update function.

    Args:
        metric_name: Name of the metric to update
        value: Value to add (default 1.0)
    """
    with metrics_lock:
        if metric_name in metrics:
            if metric_name == "response_times":
                metrics[metric_name].append(value)
                # Keep only last 1000 response times for memory efficiency
                if len(metrics[metric_name]) > 1000:
                    metrics[metric_name] = metrics[metric_name][-1000:]
                # Update average response time
                metrics["average_response_time"] = sum(metrics[metric_name]) / len(metrics[metric_name])
            else:
                metrics[metric_name] += value


def log_performance(func):
    """Decorator to log performance metrics for API endpoints.

    Args:
        func: Function to be decorated

    Returns:
        Wrapped function with performance logging
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        logger.info(f"[{request_id}] Starting {func.__name__} - IP: {request.remote_addr}")
        update_metrics("total_requests")

        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            response_time = end_time - start_time

            update_metrics("successful_requests")
            update_metrics("response_times", response_time)

            logger.info(f"[{request_id}] Completed {func.__name__} - Response time: {response_time:.3f}s")
            return result

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time

            update_metrics("failed_requests")
            update_metrics("response_times", response_time)

            logger.error(
                f"[{request_id}] Failed {func.__name__} - Error: {str(e)} - Response time: {response_time:.3f}s"
            )
            raise

    return wrapper


def search_google(
    query: str,
    api_key: str,
    cse_id: str,
    num: int = 10,
    safe_search: bool = True,
    language: str = "en",
    country: str = "US",
    request_id: str = None,
) -> Tuple[List[Dict], bool]:
    """Performs a Google search using direct HTTP requests and returns a list of results.

    Args:
        query: The search query string.
        api_key: Your Google API key.
        cse_id: Your Google Custom Search Engine ID.
        num: Number of search results to return.
        safe_search: Whether to enable safe search. Defaults to True.
        language: The language of the search results (e.g., 'en', 'es'). Defaults to 'en'.
        country: The country to tailor the search results to (e.g., 'US', 'GB'). Defaults to 'US'.
        request_id: Request ID for logging purposes.

    Returns:
        A tuple containing:
        - List of dictionaries, where each dictionary contains 'url' and 'abstract'
        - Boolean indicating success status
    """
    if not api_key or not cse_id:
        logger.error(f"[{request_id}] API key or CSE ID not provided for query: {query}")
        update_metrics("failed_searches")
        return [], False

    results = []
    service_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": num,
        "safe": "active" if safe_search else "off",
        "hl": language,
        "gl": country,
    }

    search_start = time.time()
    update_metrics("total_searches")

    try:
        logger.info(f"[{request_id}] Executing Google search for query: '{query}'")
        response = requests.get(service_url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if "items" in data:
            for item in data["items"]:
                results.append({"url": item.get("link"), "abstract": item.get("snippet")})

            search_time = time.time() - search_start
            logger.info(
                f"[{request_id}] Google search completed for '{query}' - Found {len(results)} results in {search_time:.3f}s"
            )
            update_metrics("successful_searches")
            return results, True
        else:
            logger.warning(f"[{request_id}] No items found in Google search response for query: '{query}'")
            update_metrics("successful_searches")  # Still successful, just no results
            return [], True

    except requests.exceptions.RequestException as e:
        search_time = time.time() - search_start
        logger.error(f"[{request_id}] Request error during Google search for '{query}': {e} - Time: {search_time:.3f}s")
        update_metrics("failed_searches")
        return [], False
    except json.JSONDecodeError as e:
        search_time = time.time() - search_start
        logger.error(f"[{request_id}] JSON decode error for '{query}': {e} - Time: {search_time:.3f}s")
        update_metrics("failed_searches")
        return [], False
    except Exception as e:
        search_time = time.time() - search_start
        logger.error(
            f"[{request_id}] Unexpected error during Google search for '{query}': {e} - Time: {search_time:.3f}s"
        )
        update_metrics("failed_searches")
        return [], False


def fetch_web_content(url: str, request_id: str = None, max_len: Optional[int] = 8*1024) -> Tuple[str, bool, bool]:
    """Fetches and extracts readable text content from a given URL using BeautifulSoup.

    Args:
        url: The URL of the web page.
        request_id: Request ID for logging purposes.
        max_len: Maximum length of the content to fetch.

    Returns:
        A tuple containing:
        - The extracted text content of the web page (truncated if necessary)
        - Boolean indicating success status
        - Boolean indicating whether the content was truncated
    """
    fetch_start = time.time()
    update_metrics("total_content_fetches")

    try:
        logger.info(f"[{request_id}] Fetching content from: {url}")
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (compatible; SearchBot/1.0)"}
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text
        text = soup.get_text()

        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = "\n".join(chunk for chunk in chunks if chunk)

        # Check if truncation is needed
        is_truncated = max_len is not None and len(text) > max_len
        if is_truncated:
            text = text[:max_len]

        fetch_time = time.time() - fetch_start
        content_length = len(text)
        truncation_info = " (truncated)" if is_truncated else ""
        logger.info(
            f"[{request_id}] Successfully fetched content from {url} - Length: {content_length} chars{truncation_info} - Time: {fetch_time:.3f}s"
        )
        update_metrics("successful_content_fetches")

        return text, True, is_truncated

    except requests.exceptions.RequestException as e:
        fetch_time = time.time() - fetch_start
        logger.error(f"[{request_id}] Request error while fetching content from {url}: {e} - Time: {fetch_time:.3f}s")
        update_metrics("failed_content_fetches")
        return "", False, False
    except Exception as e:
        fetch_time = time.time() - fetch_start
        logger.error(f"[{request_id}] Unexpected error while parsing content from {url}: {e} - Time: {fetch_time:.3f}s")
        update_metrics("failed_content_fetches")
        return "", False, False


def process_single_query(
    query: str,
    api_key: str,
    cse_id: str,
    num_results: int,
    language: str,
    country: str,
    safe_search: bool,
    request_id: str,
    max_len: Optional[int] = None,
) -> Tuple[str, List[Dict]]:
    """Process a single query with concurrent content fetching.

    Args:
        query: Search query string
        api_key: Google API key
        cse_id: Google Custom Search Engine ID
        num_results: Number of results to fetch
        language: Search language
        country: Search country
        safe_search: Safe search setting
        request_id: Request ID for logging
        max_len: Maximum content length (optional)

    Returns:
        Tuple of (query, results_list)
    """
    logger.info(f"[{request_id}] Processing query: {query}")
    query_start = time.time()

    # Perform Google search
    search_results, search_success = search_google(
        query,
        api_key,
        cse_id,
        num=num_results,
        safe_search=safe_search,
        language=language,
        country=country,
        request_id=request_id,
    )

    if not search_success or not search_results:
        logger.warning(f"[{request_id}] No search results or search failed for query: {query}")
        return query, []

    # Fetch content concurrently for all URLs
    query_output = []

    def fetch_single_result(result):
        """Helper function to fetch content for a single result."""
        url = result.get("url")
        abstract = result.get("abstract")

        if url:
            if max_len is not None:
                content, fetch_success, is_truncated = fetch_web_content(url, request_id, max_len)
            else:
                content, fetch_success, is_truncated = fetch_web_content(url, request_id)
            return {url: {"abs": abstract, "content": content, "fetch_success": fetch_success, "is_truncated": is_truncated}}
        else:
            logger.warning(f"[{request_id}] Skipping result with no URL for query: {query}")
            return None

    # Use ThreadPoolExecutor for concurrent content fetching
    with ThreadPoolExecutor(max_workers=min(MAX_CONTENT_WORKERS, len(search_results))) as executor:
        future_to_result = {executor.submit(fetch_single_result, result): result for result in search_results}

        for future in as_completed(future_to_result):
            try:
                result_data = future.result()
                if result_data:
                    query_output.append(result_data)
            except Exception as e:
                logger.error(f"[{request_id}] Error processing result for query '{query}': {e}")

    query_time = time.time() - query_start
    logger.info(
        f"[{request_id}] Completed processing query: {query} - Results: {len(query_output)} - Time: {query_time:.3f}s"
    )

    return query, query_output


def process_queries_concurrent(
    queries: List[str],
    api_key: str,
    cse_id: str,
    num_results: int = NUM_RESULTS,
    language: str = "en",
    country: str = "US",
    safe_search: bool = True,
    request_id: str = None,
) -> Dict[str, List]:
    """Processes a list of search queries concurrently, fetches results and content.

    Args:
        queries: A list of search query strings.
        api_key: Google API key.
        cse_id: Google Custom Search Engine ID.
        num_results: Number of results per query.
        language: Search language.
        country: Search country.
        safe_search: Safe search setting.
        request_id: Request ID for logging.

    Returns:
        A dictionary structured as
        {"query1":[{"url1":{"abs":"xxx", "content":"yyy"}}, ...], ...}
    """
    if not api_key or not cse_id:
        logger.error(f"[{request_id}] CRITICAL ERROR: API key or CSE ID not provided. Aborting search process.")
        return {query: [] for query in queries}

    logger.info(f"[{request_id}] Starting concurrent processing of {len(queries)} queries")
    process_start = time.time()

    output_data = {}

    # Process queries concurrently
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(queries))) as executor:
        future_to_query = {
            executor.submit(
                process_single_query, query, api_key, cse_id, num_results, language, country, safe_search, request_id
            ): query
            for query in queries
        }

        for future in as_completed(future_to_query):
            try:
                query, results = future.result()
                output_data[query] = results
            except Exception as e:
                query = future_to_query[future]
                logger.error(f"[{request_id}] Error processing query '{query}': {e}")
                output_data[query] = []

    process_time = time.time() - process_start
    successful_queries = sum(1 for results in output_data.values() if results)

    logger.info(
        f"[{request_id}] Completed concurrent processing - Total queries: {len(queries)}, Successful: {successful_queries}, Time: {process_time:.3f}s"
    )

    return output_data


# Flask Routes
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint with system metrics."""
    with metrics_lock:
        current_metrics = metrics.copy()

    # Calculate success rates
    request_success_rate = (current_metrics["successful_requests"] / max(current_metrics["total_requests"], 1)) * 100
    search_success_rate = (current_metrics["successful_searches"] / max(current_metrics["total_searches"], 1)) * 100
    content_success_rate = (
        current_metrics["successful_content_fetches"] / max(current_metrics["total_content_fetches"], 1)
    ) * 100

    return jsonify(
        {
            "status": "healthy",
            "service": "search-server",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "requests": {
                    "total": current_metrics["total_requests"],
                    "successful": current_metrics["successful_requests"],
                    "failed": current_metrics["failed_requests"],
                    "success_rate": round(request_success_rate, 2),
                },
                "searches": {
                    "total": current_metrics["total_searches"],
                    "successful": current_metrics["successful_searches"],
                    "failed": current_metrics["failed_searches"],
                    "success_rate": round(search_success_rate, 2),
                },
                "content_fetches": {
                    "total": current_metrics["total_content_fetches"],
                    "successful": current_metrics["successful_content_fetches"],
                    "failed": current_metrics["failed_content_fetches"],
                    "success_rate": round(content_success_rate, 2),
                },
                "performance": {
                    "average_response_time": round(current_metrics["average_response_time"], 3),
                    "max_workers": MAX_WORKERS,
                    "max_content_workers": MAX_CONTENT_WORKERS,
                },
            },
        }
    )


@app.route("/search", methods=["POST"])
@log_performance
def search_endpoint():
    """Main search endpoint that accepts POST requests with queries.

    Expected JSON payload:
    {
        "api_key": "your_google_api_key",
        "cse_id": "your_google_cse_id",
        "queries": ["query1", "query2", ...],
        "num_results": 5,  // optional, defaults to NUM_RESULTS
        "language": "en",  // optional, defaults to "en"
        "country": "US",   // optional, defaults to "US"
        "safe_search": true,  // optional, defaults to true
        "max_len": 8192  // optional, content truncation length
    }
    """
    request_id = str(uuid.uuid4())[:8]

    try:
        # Validate request
        if not request.is_json:
            logger.warning(f"[{request_id}] Non-JSON request received")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        required_fields = ["api_key", "cse_id", "queries"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"[{request_id}] Missing required field: '{field}'")
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        if not isinstance(data["queries"], list):
            logger.warning(f"[{request_id}] 'queries' field is not a list")
            return jsonify({"error": "'queries' must be a list"}), 400

        if not data["queries"]:
            logger.warning(f"[{request_id}] Empty queries list provided")
            return jsonify({"error": "'queries' list cannot be empty"}), 400

        # Extract parameters
        api_key = data["api_key"]
        cse_id = data["cse_id"]
        queries = data["queries"]
        num_results = data.get("num_results", NUM_RESULTS)
        language = data.get("language", "en")
        country = data.get("country", "US")
        safe_search = data.get("safe_search", True)
        max_len = data.get("max_len")

        # Validate parameters
        if not isinstance(num_results, int) or num_results <= 0 or num_results > 10:
            logger.warning(f"[{request_id}] Invalid num_results value: {num_results}")
            return jsonify({"error": "'num_results' must be an integer between 1 and 10"}), 400

        if not api_key.strip() or not cse_id.strip():
            logger.warning(f"[{request_id}] Empty API key or CSE ID provided")
            return jsonify({"error": "'api_key' and 'cse_id' cannot be empty"}), 400

        logger.info(
            f"[{request_id}] Processing search request - Queries: {len(queries)}, Results per query: {num_results}"
        )

        # Process queries concurrently
        results = process_queries_concurrent(
            queries, api_key, cse_id, num_results, language, country, safe_search, request_id, max_len
        )

        return jsonify(
            {
                "success": True,
                "request_id": request_id,
                "results": results,
                "query_count": len(queries),
                "parameters": {
                    "num_results": num_results,
                    "language": language,
                    "country": country,
                    "safe_search": safe_search,
                    "max_len": max_len,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"[{request_id}] Error in search endpoint: {e}")
        return jsonify({"error": "Internal server error", "request_id": request_id}), 500


@app.route("/search/single", methods=["POST"])
@log_performance
def single_search_endpoint():
    """Simplified endpoint for single query searches with enhanced performance.

    Expected JSON payload:
    {
        "api_key": "your_google_api_key",
        "cse_id": "your_google_cse_id",
        "query": "search term",
        "num_results": 5,  // optional
        "fetch_content": true,  // optional, defaults to true
        "language": "en",  // optional
        "country": "US",   // optional
        "safe_search": true,  // optional
        "max_len": 8192  // optional, content truncation length
    }
    """
    request_id = str(uuid.uuid4())[:8]

    try:
        if not request.is_json:
            logger.warning(f"[{request_id}] Non-JSON request received")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        required_fields = ["api_key", "cse_id", "query"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"[{request_id}] Missing required field: '{field}'")
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        api_key = data["api_key"]
        cse_id = data["cse_id"]
        query = data["query"]
        num_results = data.get("num_results", NUM_RESULTS)
        fetch_content = data.get("fetch_content", True)
        language = data.get("language", "en")
        country = data.get("country", "US")
        safe_search = data.get("safe_search", True)
        max_len = data.get("max_len")

        if not api_key.strip() or not cse_id.strip():
            logger.warning(f"[{request_id}] Empty API key or CSE ID provided")
            return jsonify({"error": "'api_key' and 'cse_id' cannot be empty"}), 400

        logger.info(
            f"[{request_id}] Processing single search request - Query: '{query}', Fetch content: {fetch_content}"
        )

        # Perform search
        search_results, search_success = search_google(
            query,
            api_key,
            cse_id,
            num=num_results,
            safe_search=safe_search,
            language=language,
            country=country,
            request_id=request_id,
        )

        if not search_success:
            logger.error(f"[{request_id}] Search failed for query: '{query}'")
            return jsonify({"error": "Search failed", "request_id": request_id}), 500

        if fetch_content and search_results:
            # Fetch content concurrently for each result
            enhanced_results = []

            def fetch_result_content(result):
                """Helper function to fetch content for a single search result."""
                url = result.get("url")
                abstract = result.get("abstract")
                if url:
                    if max_len is not None:
                        content, fetch_success, is_truncated = fetch_web_content(url, request_id, max_len)
                    else:
                        content, fetch_success, is_truncated = fetch_web_content(url, request_id)
                    return {"url": url, "abstract": abstract, "content": content, "fetch_success": fetch_success, "is_truncated": is_truncated}
                return None

            with ThreadPoolExecutor(max_workers=min(MAX_CONTENT_WORKERS, len(search_results))) as executor:
                future_to_result = {executor.submit(fetch_result_content, result): result for result in search_results}

                for future in as_completed(future_to_result):
                    try:
                        result_data = future.result()
                        if result_data:
                            enhanced_results.append(result_data)
                    except Exception as e:
                        logger.error(f"[{request_id}] Error fetching content for result: {e}")

            return jsonify(
                {
                    "success": True,
                    "request_id": request_id,
                    "query": query,
                    "results": enhanced_results,
                    "count": len(enhanced_results),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "request_id": request_id,
                    "query": query,
                    "results": search_results,
                    "count": len(search_results),
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except Exception as e:
        logger.error(f"[{request_id}] Error in single search endpoint: {e}")
        return jsonify({"error": "Internal server error", "request_id": request_id}), 500


@app.route("/search/agentic", methods=["POST"])
@log_performance
def agentic_search_endpoint():
    """Advanced search endpoint using handle_single_query function.

    Expected JSON payload:
    {
        "question": "user question",
        "search_queries": ["query1", "query2", "query3"],
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "serper_api_key": "your_serper_api_key",
        "topk": 5  // optional, defaults to 5
    }
    """
    request_id = str(uuid.uuid4())[:8]

    try:
        if not request.is_json:
            logger.warning(f"[{request_id}] Non-JSON request received")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        required_fields = ["question", "search_queries", "base_url", "api_key", "serper_api_key"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"[{request_id}] Missing required field: '{field}'")
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        question = data["question"]
        search_queries = data["search_queries"]
        base_url = data["base_url"]
        api_key = data["api_key"]
        serper_api_key = data["serper_api_key"]
        topk = data.get("topk", 5)

        # Validate input types
        if not isinstance(search_queries, list):
            logger.warning(f"[{request_id}] search_queries must be a list")
            return jsonify({"error": "search_queries must be a list"}), 400

        if not search_queries:
            logger.warning(f"[{request_id}] search_queries cannot be empty")
            return jsonify({"error": "search_queries cannot be empty"}), 400

        logger.info(
            f"[{request_id}] Processing advanced search request - Question: '{question}', "
            f"Queries: {search_queries}, TopK: {topk}"
        )

        # Create auth args
        auth_args = AuthArgs(base_url=base_url, api_key=api_key, serper_api_key=serper_api_key)

        # Call handle_single_query function
        search_results: SearchResults = handle_single_query(
            question=question, search_query_list=search_queries, auth_args=auth_args, topk=topk
        )

        # Check if results are valid
        if not search_results or not search_results.search_results:
            logger.warning(f"[{request_id}] No search results returned")
            return jsonify({"error": "No search results found", "request_id": request_id}), 404

        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "question": question,
            "search_queries": search_queries,
            "results": search_results.model_dump(),
            "total_results": len(search_results.search_results),
        }

        logger.info(f"[{request_id}] Agentic search completed successfully")
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"[{request_id}] Agentic search failed: {str(e)}")
        return jsonify({"error": "Internal server error", "request_id": request_id, "details": str(e)}), 500


class Answer(BaseModel):
    important_records: str
    final_answer: str

async def run_browser_agent(question,browser_port,user_data_dir,model_name,api_key,base_url,temperature,enable_memory):
    controller = Controller(output_model=Answer)
    command = [
        "/usr/bin/google-chrome",
        "--remote-debugging-port="+browser_port,
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir="+user_data_dir,
        # "--headless",  # 启用无头模式
        # "--disable-gpu",  # 禁用 GPU 加速（可选）
        # "--window-size=1920,1080"  # 设置窗口大小（可选）
    ]
    process = subprocess.Popen(command)

    browser = Browser(
        config=BrowserConfig(
            # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
            browser_binary_path='/usr/bin/google-chrome',
            chrome_remote_debugging_port=browser_port,
            new_context_config=BrowserContextConfig(no_viewport=False),
            # headless=True,
        )
    )
    llm=ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )
    page_extraction_llm=ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )
    # memory_config=MemoryConfig( # Ensure llm_instance is passed if not using default LLM config
    #     llm_instance=page_extraction_llm,      # Important: Pass the agent's LLM instance here
    #     agent_id="browser_agent_01",
    #     memory_interval=10,
    # )

    task=question
    agent = Agent(
        task=task,
        llm=llm,
        page_extraction_llm=page_extraction_llm,
        # browser_session=browser_session,
        browser=browser,
        controller=controller,
        tool_calling_method="raw",
        # memory_config=memory_config,
        enable_memory=enable_memory,
    )

    history=None
    parsed=None
    try:
        history = await agent.run()
        result = history.final_result()
        parsed: Answer = Answer.model_validate_json(result)
    except Exception as e:
        print(e)
    finally:
        await browser.close()
        process.terminate()
        return parsed

@app.route("/browser/agentic", methods=["POST"])
@log_performance
def agentic_browser_endpoint():
    """Advanced search endpoint using handle_single_query function.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "model_name": "your_model_name",
        "browser_port": "the_browser_port"
    }
    """
    request_id = str(uuid.uuid4())[:8]

    try:
        if not request.is_json:
            logger.warning(f"[{request_id}] Non-JSON request received")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        required_fields = ["question", "base_url", "api_key", "model_name"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"[{request_id}] Missing required field: '{field}'")
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        question = data["question"]
        base_url = data["base_url"]
        api_key = data["api_key"]
        model_name = data["model_name"]
        browser_port = data.get("browser_port","9111")

        enable_memory=False
        temperature=0.3
        user_data_dir = "/tmp/chrome-debug/0000"

        
        parsed=asyncio.run(run_browser_agent(question,browser_port,user_data_dir,model_name,api_key,base_url,temperature,enable_memory))

        ans={}
        if parsed:
            print('\n--------------------------------')
            print(f'important_records:         {parsed.important_records}')
            print(f'model_answer:              {parsed.final_answer}')
        
            ans={"important_records":parsed.important_records,"final_answer":parsed.final_answer}


        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "question": question,
            "results": ans,
        }

        logger.info(f"[{request_id}] Agentic search completed successfully")
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"[{request_id}] Agentic search failed: {str(e)}")
        return jsonify({"error": "Internal server error", "request_id": request_id, "details": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting Flask search server with enhanced concurrency and logging...")
    logger.info(
        f"Configuration - Max workers: {MAX_WORKERS}, Max content workers: {MAX_CONTENT_WORKERS}, Request timeout: {REQUEST_TIMEOUT}s"
    )
    logger.info("API credentials will be provided via request parameters")

    # Run Flask app
    SEARCH_PORT = os.getenv("SEARCH_PORT", "19090")

    try:
        SEARCH_PORT = int(SEARCH_PORT)
    except Exception as e:
        logger.warning(f"Invalid SEARCH_PORT value, using default 19090: {e}")
        SEARCH_PORT = 19090

    logger.info(f"Server starting on port {SEARCH_PORT}")
    app.run(host="0.0.0.0", port=SEARCH_PORT, debug=False, threaded=True)
