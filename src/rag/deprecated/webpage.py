from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.rag.browser.text_web_browser import SimpleTextBrowser

QUICK_SUMMARY_PROMPT = """You are an AI assistant analyzing webpage content to determine if it's helpful for answering a user's question. Given:

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
* The user's main question. This is a complex question that requires a deep research to answer.
* A sub-question. The main question has been broken down into a set of sub-questions to help you focus on specific aspects of the main question, and this sub-question is the current focus.
* The context so far. This includes all the information that has been gathered from previous turns, including the sub-questions and the information gathered from other resources for them.
* One page of a webpage content as well as the page index. We do paging because the content of a webpage is usually long and we want to provide you with a manageable amount of information at a time. So please mind the page index to know which page you are reading as this could help you infer what could appear in other pages.

Your task is to read the webpage content carefully and extract all *new* information (compared to the context so far) that could help answer either the main question or the sub-question. So you should only gather incremental information from this webpage, but if you find additional details that can complete the previous context, please include them. If you find contradictory information, also include them for further analysis. Provide detailed information including numbers, dates, facts, examples, and explanations when available. Keep the original information as possible, but you can summarize if needed.

In addition to the extracted information, you should also think about whether we need to read more content from this webpage to get more detailed information by paing down to read more content. Also, add a very short summary of the extracted information to help the user understand the new information.


Note that there could be no useful information on the webpage.

Your answer should follow the following format: 
* Put the extracted new information in <extracted_info> tag. If there is no new information, leave the <extracted_info> tag empty. Do your best to get as much information as possible.
* Put "yes" or "no" in <page_down> tag. This will be used for whether to do page down to read more content from the web. For example, if you find the extracted information is from the introduction section in a paper, then you can infer that the extracted information could miss detailed information, next round can further read more content for details in this web page by paging down. If this already the last page, always put "no" in <page_down> tag.
* Put the short summary of the extracted information in <short_summary> tag. Try your best to make it short but also informative as this will present to the user to notify your progress. If there is no useful new information, please also say something like "Didn't find useful information, will read more" in the short summary (be free to use your own words). 

Important note: Use the same language as the user's main question for the short summary. For example, if the main question is using Chinese, then the short summary should also be in Chinese.

<main_question>
{main_question}
</main_question>

<context_so_far>
{context_so_far}
</context_so_far>

<current_sub_question>
{sub_question}
<current_sub_question>

<webpage_content>
    <page_index>{page_index}</page_index>
    <total_page_number>{total_pages}</total_page_number>
    <current_page_content>{page_content}</current_page_content>
</webpage_content>

Now think and extract the incremental information that could help answer the main question or the sub-question."""


class WebSelectInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    web_select_thinking: str = Field(..., description="think about whether to select this web page")
    web_select_idx: str = Field(..., description="the index of the web page")

    # def __init__(self, web_select_thinking: str, web_select_idx: int):
    #     self.web_select_thinking: str = web_select_thinking
    #     self.web_select_idx: int = web_select_idx

    def to_dict(self) -> dict[str, Any]:
        return {"web_select_thinking": self.web_select_thinking, "web_select_idx": self.web_select_idx}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebSelectInfo":
        return cls(web_select_thinking=data["web_select_thinking"], web_select_idx=data["web_select_idx"])

    # def __str__(self) -> str:
    #     return (
    #         f"WebSelectInfo(idx={self.web_select_idx}, "
    #         f"thinking='{self.web_select_thinking[:50]}...' "
    #         f"if len(self.web_select_thinking) > 50 else '{self.web_select_thinking}')"
    #     )


class PageReadInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    search_results_idx: int = Field(..., description="the index of the search result")
    url: str = Field(..., description="the url of the web page")
    page_title: str = Field(..., description="the title of the web page")
    fetch_res: str = Field(..., description="the fetch result of the web page")
    page_thinking: str = Field(..., description="the thinking of the web page")
    page_summary: str = Field(..., description="the summary of the web page")
    page_number: int = Field(..., description="the page number of the web page")
    need_page_down: bool = Field(..., description="whether to need page down to read more content")
    used: bool = Field(False, description="whether the page has been used")
    # def __init__(
    #     self,
    #     search_results_idx: int,
    #     url: str,
    #     page_title: str,
    #     fetch_res: str,
    #     page_thinking: str,
    #     page_summary: str,
    #     page_number: int,
    #     need_page_down: bool,
    #     used: bool = False,
    # ):
    #     self.search_results_idx = search_results_idx
    #     self.url = url
    #     self.page_title = page_title
    #     self.fetch_res = fetch_res
    #     self.page_thinking = page_thinking
    #     self.page_summary = page_summary
    #     self.page_number = page_number
    #     self.need_page_down = need_page_down
    #     self.used = used

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_results_idx": self.search_results_idx,
            "url": self.url,
            "page_title": self.page_title,
            "fetch_res": self.fetch_res,
            "page_thinking": self.page_thinking,
            "page_summary": self.page_summary,
            "page_number": self.page_number,
            "need_page_down": self.need_page_down,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageReadInfo":
        return cls(
            search_results_idx=data["search_results_idx"],
            url=data["url"],
            page_title=data["page_title"],
            fetch_res=data["fetch_res"],
            page_thinking=data["page_thinking"],
            page_summary=data["page_summary"],
            page_number=data["page_number"],
            need_page_down=data["need_page_down"],
        )

    # def __str__(self):
    #     return (
    #         f"PageReadInfo(search_results_idx={self.search_results_idx}, "
    #         f"url='{self.url}', "
    #         f"page_title='{self.page_title}', "
    #         f"page_number={self.page_number}, "
    #         f"need_page_down={self.need_page_down}, "
    #         f"page_summary='{self.page_summary[:50]}...' if len(self.page_summary) > 50 else '{self.page_summary}')"
    #     )


class WebPageInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = Field(..., description="the title of the web page")
    url: str = Field(..., description="the url of the web page")
    quick_summary: str = Field(..., description="the quick summary of the web page")
    sub_question: str = Field(..., description="the sub question of the web page")
    page_read_info_list: list[PageReadInfo] = Field(default=[], description="the list of page read info")
    browser: SimpleTextBrowser | None = Field(default=None, description="SimpleTextBrowser instance", exclude=True)

    # def __init__(self, title: str, url: str, quick_summary: str, sub_question, browser: SimpleTextBrowser = None):
    #     self.title = title
    #     self.url = url
    #     self.quick_summary = quick_summary
    #     self.browser = browser
    #     self.sub_question = sub_question
    #     self.page_read_info_list: list[PageReadInfo] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "quick_summary": self.quick_summary,
            # Note: browser object might not be serializable directly,
            # consider adding a separate serialization method if needed
            "sub_question": self.sub_question,
            "page_read_info_list": [info.to_dict() for info in self.page_read_info_list],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], browser=None) -> "WebPageInfo":
        web_page_info = cls(
            title=data["title"],
            url=data["url"],
            quick_summary=data["quick_summary"],
            browser=browser,  # Browser needs to be passed separately or reconstructed
            sub_question=data["sub_question"],
        )

        # Reconstruct page_read_info_list
        web_page_info.page_read_info_list = [
            PageReadInfo.from_dict(info_data) for info_data in data.get("page_read_info_list", [])
        ]

        return web_page_info

    # def __str__(self) -> str:
    #     base_info = f"WebPage: {self.title}\nURL: {self.url}\nQuick Summary: {self.quick_summary}\nSub Question: {self.sub_question}"

    #     if self.page_read_info_list:
    #         read_info = "\nDetailed Information:"
    #         for idx, info in enumerate(self.page_read_info_list, 1):
    #             read_info += f"\n  {idx}. {str(info)}"
    #         return base_info + read_info

    #     return base_info


class SearchResultInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    search_query: str = Field(..., description="the search query")
    web_page_info_list: list[WebPageInfo] = Field(..., description="the list of web page info")
    web_select_info_list: list[WebSelectInfo] = Field(default=[], description="the list of web select info")
    # def __init__(self, search_query, web_page_info_list: list[WebPageInfo]):
    #     self.search_query = search_query
    #     self.web_page_info_list = web_page_info_list
    #     self.web_select_info_list: list[WebSelectInfo] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_query": self.search_query,
            "web_page_info_list": [info.to_dict() for info in self.web_page_info_list],
            "web_select_info_list": [info.to_dict() for info in self.web_select_info_list],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResultInfo":
        instance = cls(
            search_query=data["search_query"],
            web_page_info_list=[WebPageInfo.from_dict(info) for info in data["web_page_info_list"]],
        )
        if "web_select_info_list" in data:
            instance.web_select_info_list = [WebSelectInfo.from_dict(info) for info in data["web_select_info_list"]]
        return instance

    # def __str__(self) -> str:
    #     result = "SearchResultInfo:\n"
    #     result += f"  Query: {self.search_query}\n"
    #     result += f"  Found {len(self.web_page_info_list)} web pages:\n"

    #     for idx, page_info in enumerate(self.web_page_info_list, 1):
    #         result += f"    {idx}. {page_info.title} - {page_info.url}\n"

    #     if self.web_select_info_list:
    #         result += f"  Selected {len(self.web_select_info_list)} pages for detailed reading\n"

    #     return result.rstrip()
