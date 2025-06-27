import concurrent.futures
import copy
import json
import logging
import os
import threading
import time

import requests
from utils import *
from webpage import QUICK_SUMMARY_PROMPT, WebPageInfo

from src.rag.browser.text_web_browser import SimpleTextBrowser

logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    format="%(asctime)s - %(levelname)s - %(message)s",  # 设置日志格式
)


def web_search(query, config, serper_api_key):
    def serper_google_search(query, serper_api_key, top_k, region, lang):
        try:
            url = "https://google.serper.dev/search"
            headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
            payload = json.dumps(
                {
                    "q": query,
                    "num": top_k,
                    "gl": region,
                    "hl": lang,
                }
            )
            response = requests.request("POST", url, headers=headers, data=payload)
            data = json.loads(response.text)

            if not data:
                raise Exception("The google search API is temporarily unavailable, please try again later.")

            if "organic" not in data:
                raise Exception(f"No results found for query: '{query}'. Use a less specific query.")
            else:
                results = data["organic"]
                print("search success")
                return results
        except Exception as e:
            print(f"Serper search API error: {e}")
        print("search failed")
        return []

    if not query:
        raise ValueError("Search query cannot be empty")
    if config["search_engine"] == "google":
        return serper_google_search(
            query=query,
            serper_api_key=serper_api_key,
            top_k=config["search_top_k"],
            region=config["search_region"],
            lang=config["search_lang"],
        )
    else:
        raise NotImplementedError(f"Illegal {config["search_engine"]=}")


class WebSearchAgent:
    def __init__(self, client, config, serper_api_key):
        self.client = client
        self.config = config
        self.serper_api_key = serper_api_key
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"

        self.BROWSER_CONFIG = {
            "viewport_size": 1024 * 5 * 8,
            "downloads_folder": "downloads_folder",
            "request_kwargs": {
                "headers": {"User-Agent": self.user_agent},
                "timeout": (5, 10),
            },
            "serper_api_key": serper_api_key,
        }
        downloads_folder_path = f"./{self.BROWSER_CONFIG['downloads_folder']}"
        if not os.path.exists(downloads_folder_path):
            logging.info(f"保存目录不存在，创建目录：{os.path.abspath(downloads_folder_path)}")
            os.makedirs(downloads_folder_path, exist_ok=True)

        self.search_history = {}
        self.search_history_lock = threading.Lock()
        self.url_browser_dict = {}
        self.url_browser_dict_lock = threading.Lock()

    def save(self):
        with open(self.config.query_save_path, "w", encoding="utf-8") as f:
            json.dump(self.search_history, f, indent=4, ensure_ascii=False)
        print("保存完毕")

    def browser_to_json(self, browser: SimpleTextBrowser, title: str, url: str):
        page_list = []
        total_pages = len(browser.viewport_pages)
        while browser.viewport_current_page < total_pages:
            cur_web_page_content = browser._state()[1]
            page_list.append(cur_web_page_content)
            browser.page_down()
        # 提取browser的内容，取成一个json，然后保存到数据库
        return {"title": title, "url": url, "page_list": page_list}

    def scrape(self, browser: SimpleTextBrowser, url: str) -> str:
        """爬取网页并使用LLM总结内容"""
        browser.visit_page(url)
        header, content = browser._state()
        return header.strip() + "\n=======================\n" + content

    def get_quick_summary(self, user_query, search_query, first_page_fetch_res):
        messages = [
            {"role": "system", "content": "Your are a helpful assistant."},
            {
                "role": "user",
                "content": QUICK_SUMMARY_PROMPT.format(
                    user_query=user_query, search_query=search_query, first_page_fetch_res=first_page_fetch_res
                ),
            },
        ]
        response = get_response_from_llm(
            messages=messages,
            client=self.client,
            model=self.config["quick_summary_model"],
            stream=False,
        )["content"]

        helpful = True
        summary = get_content_from_tag(response, "summary", response).strip()
        return helpful, summary

    def is_error_page(self, browser: SimpleTextBrowser) -> bool:
        if isinstance(browser.page_title, tuple):
            return True
        return (
            browser.page_title is not None
            and browser.page_title.startswith("Error ")
            and browser.page_content is not None
            and browser.page_content.startswith("## Error ")
        )

    def fetch_content(self, browser: SimpleTextBrowser, url: str):
        try:
            return self.scrape(browser, url)
        except Exception:
            # logging.error(e)
            return "## Error : No valid information in this page"

    def scrape_and_check_valid(self, web_info: dict, user_query, search_query):
        quick_summary = web_info["snippet"] if "snippet" in web_info else ""
        web_info["quick_summary"] = quick_summary
        if web_info["link"] in self.url_browser_dict:
            return copy.deepcopy(self.url_browser_dict[web_info["link"]])
        browser = SimpleTextBrowser(**self.BROWSER_CONFIG)
        content = self.fetch_content(browser, web_info["link"])
        if content is None:
            return None

        if self.is_error_page(browser):
            logging.info(f"访问错误，抛弃URL：{web_info['link']}")
            return None

        with self.url_browser_dict_lock:
            self.url_browser_dict[web_info["link"]] = copy.deepcopy(browser)

        return browser

    def scrape_and_check_valid_api(self, url):
        browser = SimpleTextBrowser(**self.BROWSER_CONFIG)
        content = self.fetch_content(browser, url)
        if content is None:
            return None

        if self.is_error_page(browser):
            logging.info(f"访问错误，抛弃URL：{url}")
            return None
        return browser

    def web_search_wrapper(self, search_query):
        if search_query in self.search_history and (
            time.time() - self.search_history[search_query]["timestamp"] <= 60 * 60 * 24
        ):
            return self.search_history[search_query]["organic"]
        organic = web_search(search_query, self.config, self.serper_api_key)
        if len(organic) > 0:
            with self.search_history_lock:
                self.search_history[search_query] = {"timestamp": time.time(), "organic": organic}
        return organic

    def search_web(self, user_query, search_query: str, api_result_dict: dict) -> list[WebPageInfo]:
        organic = api_result_dict[search_query]["organic"]
        web_info_list = []
        for site in organic:
            web_info_list.append(site)
        web_page_info_list = []
        for web_info in web_info_list:
            web_page_info_list.append(
                WebPageInfo(
                    title=web_info["title"],
                    url=web_info["link"],
                    quick_summary=web_info["snippet"] if "snippet" in web_info else "",
                    browser=None,
                    sub_question=search_query,
                )
            )
        return web_page_info_list

    def search_web_batch(
        self, user_query: str, search_query_list: list[str], api_result_dict: dict
    ) -> list[list[WebPageInfo]]:
        web_page_info_list_batch = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
            future_to_content = [
                executor.submit(self.search_web, user_query, search_query, api_result_dict)
                for search_query in search_query_list
            ]
        for i, future in enumerate(future_to_content):
            web_page_info_list = future.result()
            web_page_info_list_batch.append(web_page_info_list)
        return web_page_info_list_batch
