"""Enhanced webpage data models with comprehensive documentation and validation."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..browser.text_web_browser import SimpleTextBrowser

# LLM Prompts for content analysis
QUICK_SUMMARY_PROMPT = """You are an AI assistant analyzing webpage content to determine if it's helpful for answering a user's question.

Given:
1. User query: {user_query}
2. Search query: {search_query}
3. Webpage content: {first_page_fetch_res}

Evaluate if this webpage contains useful information for answering the user's question or search query.

Think through:
1. What key information does the webpage contain?
2. How does this information relate to the user's question or search query?
3. Is the content sufficient and relevant to help answer the query?

Provide your analysis in this format:
<helpful>yes/no</helpful>
<summary>If helpful: Concise summary of relevant information that helps answer the query</summary>"""

EXTRACT_NEW_INFO_PROMPT = """You are a helpful AI research assistant. I will provide you:
* The user's main question. This is a complex question that requires deep research to answer.
* A sub-question. The main question has been broken down into sub-questions to help focus on specific aspects.
* The context so far. This includes all information gathered from previous turns.
* One page of webpage content with page index for context.

Your task is to read the webpage content carefully and extract all *new* information (compared to the context so far) that could help answer either the main question or the sub-question.

Extract detailed information including numbers, dates, facts, examples, and explanations when available. Keep original information when possible, but summarize if needed.

Also determine if we need to read more content from this webpage by paging down.

Note: There might be no useful information on the webpage.

Your answer should follow this format:
* Put extracted new information in <extracted_info> tag. If no new information, leave empty.
* Put "yes" or "no" in <page_down> tag for whether to continue reading.
* Put short summary in <short_summary> tag.

Important: Use the same language as the user's main question for the short summary.

<main_question>
{main_question}
</main_question>

<context_so_far>
{context_so_far}
</context_so_far>

<current_sub_question>
{sub_question}
</current_sub_question>

<webpage_content>
    <page_index>{page_index}</page_index>
    <total_page_number>{total_pages}</total_page_number>
    <current_page_content>{page_content}</current_page_content>
</webpage_content>

Now extract the incremental information that could help answer the main question or sub-question."""


class WebSelectInfo(BaseModel):
    """Information about web page selection decisions.
    
    This model tracks the reasoning and decision-making process
    for selecting specific web pages for detailed analysis.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    web_select_thinking: str = Field(
        ..., 
        description="Reasoning process for web page selection",
        min_length=1
    )
    web_select_idx: str = Field(
        ..., 
        description="Index identifier of the selected web page"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the object
        """
        return {
            "web_select_thinking": self.web_select_thinking,
            "web_select_idx": self.web_select_idx
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebSelectInfo":
        """Create instance from dictionary.
        
        Args:
            data: Dictionary containing object data
            
        Returns:
            WebSelectInfo instance
        """
        return cls(
            web_select_thinking=data["web_select_thinking"],
            web_select_idx=data["web_select_idx"]
        )


class PageReadInfo(BaseModel):
    """Information about a single page reading session.
    
    This model captures all relevant information from processing
    a single page of web content, including extraction results
    and navigation decisions.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    search_results_idx: int = Field(
        ..., 
        description="Index of the search result this page belongs to",
        ge=0
    )
    url: str = Field(
        ..., 
        description="URL of the web page",
        min_length=1
    )
    page_title: str = Field(
        ..., 
        description="Title of the web page"
    )
    fetch_res: str = Field(
        ..., 
        description="Raw content fetched from the web page"
    )
    page_thinking: str = Field(
        default="", 
        description="LLM reasoning process for this page"
    )
    page_summary: str = Field(
        ..., 
        description="Extracted summary of useful information",
        min_length=1
    )
    page_number: int = Field(
        ..., 
        description="Page number within the document",
        ge=0
    )
    need_page_down: bool = Field(
        ..., 
        description="Whether more content should be read from this page"
    )
    used: bool = Field(
        default=False, 
        description="Whether this page information has been utilized"
    )

    @field_validator('url')
    def validate_url(cls, v: str) -> str:
        """Validate URL format.
        
        Args:
            v: URL string to validate
            
        Returns:
            Validated URL string
            
        Raises:
            ValueError: If URL format is invalid
        """
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the object
        """
        return {
            "search_results_idx": self.search_results_idx,
            "url": self.url,
            "page_title": self.page_title,
            "fetch_res": self.fetch_res,
            "page_thinking": self.page_thinking,
            "page_summary": self.page_summary,
            "page_number": self.page_number,
            "need_page_down": self.need_page_down,
            "used": self.used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageReadInfo":
        """Create instance from dictionary.
        
        Args:
            data: Dictionary containing object data
            
        Returns:
            PageReadInfo instance
        """
        return cls(
            search_results_idx=data["search_results_idx"],
            url=data["url"],
            page_title=data["page_title"],
            fetch_res=data["fetch_res"],
            page_thinking=data.get("page_thinking", ""),
            page_summary=data["page_summary"],
            page_number=data["page_number"],
            need_page_down=data["need_page_down"],
            used=data.get("used", False),
        )


class WebPageInfo(BaseModel):
    """Comprehensive information about a web page.
    
    This model represents a complete web page with its metadata,
    content, and processing history. It serves as the primary
    data structure for web page management throughout the system.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = Field(
        ..., 
        description="Title of the web page"
    )
    url: str = Field(
        ..., 
        description="URL of the web page",
        min_length=1
    )
    quick_summary: str = Field(
        default="", 
        description="Quick summary or snippet of the web page content"
    )
    sub_question: str = Field(
        ..., 
        description="Sub-question this page is intended to answer"
    )
    page_read_info_list: list[PageReadInfo] = Field(
        default_factory=list, 
        description="List of page reading information for each processed page"
    )
    browser: Optional[SimpleTextBrowser] = Field(
        default=None, 
        description="Browser instance for content access",
        exclude=True  # Exclude from serialization
    )

    @field_validator('url')
    def validate_url(cls, v: str) -> str:
        """Validate URL format.
        
        Args:
            v: URL string to validate
            
        Returns:
            Validated URL string
            
        Raises:
            ValueError: If URL format is invalid
        """
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the object
        """
        return {
            "title": self.title,
            "url": self.url,
            "quick_summary": self.quick_summary,
            "sub_question": self.sub_question,
            "page_read_info_list": [info.to_dict() for info in self.page_read_info_list],
        }

    @classmethod
    def from_dict(
        cls, 
        data: dict[str, Any], 
        browser: Optional[SimpleTextBrowser] = None
    ) -> "WebPageInfo":
        """Create instance from dictionary.
        
        Args:
            data: Dictionary containing object data
            browser: Optional browser instance
            
        Returns:
            WebPageInfo instance
        """
        web_page_info = cls(
            title=data["title"],
            url=data["url"],
            quick_summary=data.get("quick_summary", ""),
            browser=browser,
            sub_question=data["sub_question"],
        )

        # Reconstruct page_read_info_list
        web_page_info.page_read_info_list = [
            PageReadInfo.from_dict(info_data) 
            for info_data in data.get("page_read_info_list", [])
        ]

        return web_page_info

    def get_total_content_length(self) -> int:
        """Get total length of all processed content.
        
        Returns:
            Total character count of all page content
        """
        return sum(len(info.fetch_res) for info in self.page_read_info_list)

    def get_summary_text(self) -> str:
        """Get concatenated summary of all pages.
        
        Returns:
            Combined summary text from all processed pages
        """
        return "\n\n".join(info.page_summary for info in self.page_read_info_list)

    def has_useful_content(self) -> bool:
        """Check if the page contains useful extracted content.
        
        Returns:
            True if any page has useful content, False otherwise
        """
        return len(self.page_read_info_list) > 0


class SearchResultInfo(BaseModel):
    """Information about search results for a specific query.
    
    This model aggregates all web pages found for a particular
    search query, along with selection decisions and metadata.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    search_query: str = Field(
        ..., 
        description="The search query that generated these results",
        min_length=1
    )
    web_page_info_list: list[WebPageInfo] = Field(
        default_factory=list, 
        description="List of web pages found for this query"
    )
    web_select_info_list: list[WebSelectInfo] = Field(
        default_factory=list, 
        description="List of page selection decisions"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the object
        """
        return {
            "search_query": self.search_query,
            "web_page_info_list": [info.to_dict() for info in self.web_page_info_list],
            "web_select_info_list": [info.to_dict() for info in self.web_select_info_list],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResultInfo":
        """Create instance from dictionary.
        
        Args:
            data: Dictionary containing object data
            
        Returns:
            SearchResultInfo instance
        """
        instance = cls(
            search_query=data["search_query"],
            web_page_info_list=[
                WebPageInfo.from_dict(info) 
                for info in data.get("web_page_info_list", [])
            ],
        )
        
        if "web_select_info_list" in data:
            instance.web_select_info_list = [
                WebSelectInfo.from_dict(info) 
                for info in data["web_select_info_list"]
            ]
            
        return instance

    def get_total_pages(self) -> int:
        """Get total number of web pages in results.
        
        Returns:
            Total count of web pages
        """
        return len(self.web_page_info_list)

    def get_pages_with_content(self) -> list[WebPageInfo]:
        """Get pages that have useful content.
        
        Returns:
            List of pages with extracted content
        """
        return [page for page in self.web_page_info_list if page.has_useful_content()]

    def get_selected_pages(self) -> list[WebPageInfo]:
        """Get pages that were selected for detailed reading.
        
        Returns:
            List of selected web pages
        """
        selected_indices = {info.web_select_idx for info in self.web_select_info_list}
        return [
            page for i, page in enumerate(self.web_page_info_list) 
            if str(i) in selected_indices
        ]