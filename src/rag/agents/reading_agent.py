"""Enhanced reading agent for processing web content with improved error handling."""

import concurrent.futures
from typing import Any

import html2text
from openai import OpenAI

from ..core.logging import get_logger
from ..models.webpage import PageReadInfo, SearchResultInfo, WebPageInfo, EXTRACT_NEW_INFO_PROMPT
from ..utils.text_processing import get_content_from_tag, get_response_from_llm

logger = get_logger(__name__)


class ReadingAgent:
    """Agent responsible for reading and extracting information from web pages.
    
    This agent processes web content by:
    1. Reading page content in chunks
    2. Extracting relevant information using LLM
    3. Managing pagination and content flow
    4. Providing structured output for downstream processing
    """

    def __init__(self, client: OpenAI, config: dict[str, Any]) -> None:
        """Initialize the reading agent.
        
        Args:
            client: OpenAI client instance
            config: Configuration dictionary
        """
        self.client = client
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    def read(
        self,
        main_question: str,
        sub_question: str,
        selected_result_idx: int,
        cur_webpage: WebPageInfo,
        context: list[WebPageInfo] = None,
        web_search_agent: Any | None = None,
    ) -> WebPageInfo:
        """Read and extract information from a single webpage.
        
        Args:
            main_question: The main user question
            sub_question: Specific sub-question for this webpage
            selected_result_idx: Index of the selected search result
            cur_webpage: Current webpage to process
            context: List of previously processed webpages for context
            web_search_agent: Web search agent for content fetching
            
        Returns:
            Updated webpage info with extracted content
        """
        if context is None:
            context = []
            
        try:
            # Handle error cases
            if cur_webpage.browser == "error":
                self.logger.warning(f"Skipping webpage due to error: {cur_webpage.url}")
                return cur_webpage
                
            # Initialize browser if needed
            if cur_webpage.browser is None:
                if web_search_agent is None:
                    self.logger.error("Web search agent required for browser initialization")
                    cur_webpage.browser = "error"
                    return cur_webpage
                    
                cur_webpage.browser = web_search_agent.scrape_and_check_valid_api(cur_webpage.url)
                if cur_webpage.browser is None:
                    cur_webpage.browser = "error"
                    return cur_webpage

            # Build context from previous webpages
            context_so_far_prefix = self._build_context_prefix(context)
            cur_useful_info = ""
            total_pages = len(cur_webpage.browser.viewport_pages)
            
            # Process each page
            while cur_webpage.browser.viewport_current_page < total_pages:
                try:
                    page_info = self._process_single_page(
                        main_question=main_question,
                        sub_question=sub_question,
                        cur_webpage=cur_webpage,
                        context_so_far_prefix=context_so_far_prefix,
                        cur_useful_info=cur_useful_info,
                        selected_result_idx=selected_result_idx,
                        total_pages=total_pages
                    )
                    
                    if page_info["extracted_info"]:
                        cur_useful_info += page_info["extracted_info"] + "\n\n"
                        
                    if not page_info["page_down"]:
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error processing page {cur_webpage.browser.viewport_current_page}: {e}")
                    break
                    
            return cur_webpage
            
        except Exception as e:
            self.logger.error(f"Error reading webpage {cur_webpage.url}: {e}")
            cur_webpage.browser = "error"
            return cur_webpage

    def _build_context_prefix(self, context: list[WebPageInfo]) -> str:
        """Build context string from previous webpages.
        
        Args:
            context: List of previously processed webpages
            
        Returns:
            Formatted context string
        """
        context_prefix = ""
        for webpage in context:
            useful_info = ""
            for page_read_info in webpage.page_read_info_list:
                useful_info += page_read_info.page_summary + "\n\n"
            if useful_info:
                context_prefix += (
                    f"<sub_question>{webpage.sub_question}</sub_question>\n"
                    f"<useful_info>{useful_info}</useful_info>\n"
                )
        return context_prefix

    def _process_single_page(
        self,
        main_question: str,
        sub_question: str,
        cur_webpage: WebPageInfo,
        context_so_far_prefix: str,
        cur_useful_info: str,
        selected_result_idx: int,
        total_pages: int
    ) -> dict[str, Any]:
        """Process a single page of content.
        
        Args:
            main_question: Main user question
            sub_question: Current sub-question
            cur_webpage: Current webpage being processed
            context_so_far_prefix: Context from previous pages
            cur_useful_info: Information gathered so far
            selected_result_idx: Index of selected result
            total_pages: Total number of pages
            
        Returns:
            Dictionary with extracted info and navigation decision
        """
        # Build current context
        context_so_far = ""
        if cur_useful_info:
            context_so_far = (
                context_so_far_prefix +
                f"<sub_question>{sub_question}</sub_question>\n"
                f"<useful_info>{cur_useful_info}</useful_info>"
            )
        else:
            context_so_far = context_so_far_prefix

        # Get current page content
        cur_web_page_content = cur_webpage.browser._state()[1]
        cur_web_page_content = html2text.html2text(cur_web_page_content)
        page_index = cur_webpage.browser.viewport_current_page + 1

        # Create prompt for LLM
        prompt = EXTRACT_NEW_INFO_PROMPT.format(
            main_question=main_question,
            sub_question=sub_question,
            context_so_far=context_so_far.strip(),
            page_index=page_index,
            total_pages=total_pages,
            page_content=cur_web_page_content,
        )

        # Get LLM response
        messages = [{"role": "user", "content": prompt}]
        response = get_response_from_llm(
            messages=messages,
            client=self.client,
            model=self.config["reading_agent_model"],
            stream=False
        )

        # Extract information from response
        extracted_info = get_content_from_tag(response["content"], "extracted_info", "").strip()
        page_down = get_content_from_tag(response["content"], "page_down", "").strip()
        short_summary = get_content_from_tag(response["content"], "short_summary", "").strip()

        page_down_decision = "yes" in page_down.lower()

        # Store page information if useful content was extracted
        if extracted_info:
            cur_webpage.page_read_info_list.append(
                PageReadInfo(
                    search_results_idx=selected_result_idx,
                    url=cur_webpage.url,
                    page_title=cur_webpage.title,
                    fetch_res=cur_web_page_content,
                    page_thinking=response.get("reasoning_content", ""),
                    page_summary=extracted_info,
                    page_number=cur_webpage.browser.viewport_current_page,
                    need_page_down=page_down_decision,
                    used=False,
                )
            )

        # Navigate to next page if needed
        if page_down_decision:
            cur_webpage.browser.page_down()

        return {
            "extracted_info": extracted_info,
            "page_down": page_down_decision,
            "short_summary": short_summary
        }

    def read_batch(
        self,
        user_query: str,
        search_result_info_list: list[SearchResultInfo],
        url_list: list[str],
        web_search_agent: Any | None = None,
        max_workers: int = 10
    ) -> list[WebPageInfo]:
        """Read multiple webpages concurrently.
        
        Args:
            user_query: User's search query
            search_result_info_list: List of search result information
            url_list: List of URLs to process
            web_search_agent: Web search agent for content fetching
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of processed webpage information
        """
        try:
            # Create URL mapping
            url_dict = {url: [] for url in url_list}
            future_to_content = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                for search_result_info in search_result_info_list:
                    search_query = search_result_info.search_query
                    web_page_info_list = search_result_info.web_page_info_list
                    
                    for selected_result_idx, cur_webpage in enumerate(web_page_info_list):
                        if cur_webpage.url not in url_dict:
                            continue
                            
                        future = executor.submit(
                            self.read,
                            user_query,
                            search_query,
                            selected_result_idx,
                            cur_webpage,
                            web_page_info_list,
                            web_search_agent,
                        )
                        future_to_content.append(future)

            # Collect results
            read_webpage_list = []
            for future in concurrent.futures.as_completed(future_to_content):
                try:
                    cur_webpage = future.result()
                    read_webpage_list.append(cur_webpage)
                except Exception as e:
                    self.logger.error(f"Error in batch reading: {e}")
                    
            return read_webpage_list
            
        except Exception as e:
            self.logger.error(f"Batch reading failed: {e}")
            return []