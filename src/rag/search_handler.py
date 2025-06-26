import concurrent.futures
import logging
import os
import traceback
from dataclasses import dataclass
from pathlib import Path

import yaml
from openai import OpenAI
from pydantic import BaseModel, Field

from src.rag.reading_agent import ReadingAgent
from src.rag.web_search_agent import WebSearchAgent, web_search
from src.rag.webpage import PageReadInfo, SearchResultInfo, WebPageInfo

config = yaml.safe_load(open(Path(__file__).parent / "config.yml"))


@dataclass
class AuthArgs:
    base_url: str
    api_key: str
    serper_api_key: str


class WebPageDetail(BaseModel):
    title: str = Field(..., description="页面标题")
    url: str = Field(..., description="页面URL")
    quick_summary: str = Field(..., description="页面摘要")
    sub_question: str = Field(..., description="页面子问题")
    page_read_info_list: list[PageReadInfo] = Field(..., description="页面阅读信息")


def conver_web_page_info_to_detail(web_page_info: WebPageInfo) -> WebPageDetail:
    return WebPageDetail(
        title=web_page_info.title,
        url=web_page_info.url,
        quick_summary=web_page_info.quick_summary,
        sub_question=web_page_info.sub_question,
        page_read_info_list=web_page_info.page_read_info_list,
    )


class SearchResult(BaseModel):
    user_question: str = Field(..., description="用户问题")
    search_query: str = Field(..., description="搜索问题")
    search_result_info_list: list[SearchResultInfo] = Field(..., description="搜索结果")
    search_detail: dict[str, WebPageDetail] | None = Field(default=None, description="搜索详情")


class SearchResults(BaseModel):
    search_results: list[SearchResult] = Field(..., description="搜索结果列表")


def web_search_batch(search_query_list: list[str]) -> dict:
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
            future_to_content = [
                executor.submit(web_search, search_query, config) for search_query in search_query_list
            ]
        return {query: {"organic": future.result()} for query, future in zip(search_query_list, future_to_content)}
    except Exception as e:
        logging.error(f"web_search_batch error: {e}")
        return {}


def handle_single_query(
    question: str,
    search_query_list: list[str],
    auth_args: AuthArgs,
    topk: int = 5,
) -> SearchResults:
    client = OpenAI(base_url=auth_args.base_url, api_key=auth_args.api_key)
    web_search_agent = WebSearchAgent(client=client, config=config, serper_api_key=auth_args.serper_api_key)
    reading_agent = ReadingAgent(client=client, config=config)

    try:
        search_query_list = search_query_list[0:topk] if len(search_query_list) > topk else search_query_list
        api_result_dict: dict = web_search_batch(search_query_list)
        web_page_info_list_batch = web_search_agent.search_web_batch(
            user_query=question, search_query_list=search_query_list, api_result_dict=api_result_dict
        )
        search_result_info_list: list[SearchResultInfo] = []
        for search_query, web_page_info_list in zip(search_query_list, web_page_info_list_batch):
            data = {
                "search_query": search_query,
                "web_page_info_list": [info.model_dump() for info in web_page_info_list],
                "web_select_info_list": [],
            }
            search_result_info: SearchResultInfo = SearchResultInfo.model_validate(data)
            search_result_info_list.append(search_result_info)

        search_results: list[SearchResult] = []
        for search_result_info in search_result_info_list:
            search_query = search_result_info.search_query
            ret_web_page_info_list = []
            for web_page_info in search_result_info.web_page_info_list:
                ret_web_page_info_list.append(
                    {
                        "title": web_page_info.title,
                        "url": web_page_info.url,
                        "quick_summary": web_page_info.quick_summary,
                    }
                )
            search_results.append(
                SearchResult(
                    user_question=question,
                    search_query=search_query,
                    search_result_info_list=search_result_info_list,
                    search_detail=None,
                )
            )
    except Exception:
        logging.error(f"handle_single_query error: {traceback.format_exc()}")
        return []

    try:
        for search_result in search_results:
            urls: list[str] = []
            for search_info in search_result.search_result_info_list:
                for web_page_info in search_info.web_page_info_list:
                    urls.append(web_page_info.url)

            read_webpage_list: list[WebPageInfo] = reading_agent.read_batch(
                user_query=question,
                search_result_info_list=search_result.search_result_info_list,
                url_list=urls,
                web_search_agent=web_search_agent,
            )

            web_detail_dict: dict[str, WebPageDetail] = {
                read_webpage.url: conver_web_page_info_to_detail(read_webpage) for read_webpage in read_webpage_list
            }
            search_result.search_detail = web_detail_dict
        return SearchResults(search_results=search_results)
    except Exception:
        logging.error(f"handle_single_query error: {traceback.format_exc()}")
        return []


def check_health():
    auth_args = AuthArgs(
        base_url=os.getenv("base_url"),
        api_key=os.getenv("api_key"),
        serper_api_key=os.getenv("serper_api_key"),
    )
    search_results: SearchResults | None = handle_single_query("machine learning", ["machine learning"], auth_args)
    assert search_results and len(search_results) > 0, "search_results is empty"
    logging.info("DeepResearcher pipeline [search+browse+read+summary] is healthy!")


if __name__ == "__main__":
    check_health()
