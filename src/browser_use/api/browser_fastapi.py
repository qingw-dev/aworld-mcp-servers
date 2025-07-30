"""FastAPI Browser Use API routes."""
from .browser_pool import browser_semaphore
import json
import os
import subprocess
from datetime import datetime
from typing import List

from browser_use.agent.memory.views import MemoryConfig
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError
from enum import Enum
import random

from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContextConfig

from ...metrics import get_metrics_collector
from ...server_logging import get_logger
from ..utils import get_a_trace_with_img, get_oss_client, save_trace_in_oss, list_traces, get_traces_from_oss

browser_router = APIRouter(prefix="/browser", tags=["browser"])
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


class ModeEnum(str, Enum):
    SOM = 'som'
    VISUAL = 'visual'

class Answer(BaseModel):
    important_records: str
    final_answer: str


class BrowserAgentRequest(BaseModel):
    question: str|List[str]
    base_url: str
    api_key: str
    model_name: str
    temperature: float = 0.3
    enable_memory: bool = False
    browser_port: str = "9111"
    user_data_dir: str = "/tmp/chrome-debug/0000"
    headless: bool = True
    window_width: int = 1280
    window_height: int = 1100
    extract_base_url: str = ""
    extract_api_key: str = ""
    extract_model_name: str = ""
    extract_temperature: float = 0.3
    return_trace: bool = False
    save_trace: bool = True
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    trace_dir_name: str = ""
    trace_file_name: str|List[str] = ""
    max_steps: int = 100
    mode: ModeEnum = ModeEnum.SOM
    use_inner_chrome: bool = False
    google_api_key: str = ""
    google_search_engine_id: str = ""
    in_docker: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if type(self.question) == str:
            self.question = [self.question]
        if self.extract_base_url == "":
            self.extract_base_url = self.base_url
        if self.extract_api_key == "":
            self.extract_api_key = self.api_key
        if self.extract_model_name == "":
            self.extract_model_name = self.model_name
        if self.trace_dir_name == "":
            self.trace_dir_name = f"{datetime.now().strftime('%Y%m%d')}_default"
        if self.trace_file_name == "" or self.trace_file_name == [] or len(self.trace_file_name)!=len(self.question):
            for i in range(len(self.question)):
                random_number = random.randrange(100000)
                self.trace_file_name.append(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_default_{random_number:05d}")
            
class GetBrowserTraceRequest(BaseModel):
    
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    trace_file_dir: str = ""
    trace_file_name_li: List[str] = []

class ListBrowserTraceDirRequest(BaseModel):
    
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    trace_file_dir: str = ""

class BrowserTraceExistRequest(BaseModel):
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""
    trace_file_dir: str = ""
    trace_file_name: str = ""



def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")


def run_chrome_debug_mode(browser_port, user_data_dir, headless):
    browser_locate = "/usr/bin/google-chrome"
    try:
        command = [
            browser_locate,
            f"--remote-debugging-port={browser_port}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={user_data_dir}",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--font-render-hinting=none",
            "--disable-skia-runtime-opts",
            "--disable-font-subpixel-positioning",
            "--enable-unsafe-swiftshader",
            # "--headless",  # 启用无头模式
            # "--disable-gpu",  # 禁用 GPU 加速（可选）
            # "--window-size=1920,1080"  # 设置窗口大小（可选）
        ]
        if headless:
            command.append("--headless")
        process = subprocess.Popen(command)
    except Exception as e:
        print(e)
        browser_locate = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        command = [
            browser_locate,
            f"--remote-debugging-port={browser_port}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={user_data_dir}",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--font-render-hinting=none",
            "--disable-skia-runtime-opts",
            # "--headless",  # 启用无头模式
            # "--disable-gpu",  # 禁用 GPU 加速（可选）
            # "--window-size=1920,1080"  # 设置窗口大小（可选）
        ]
        if headless:
            command.append("--headless")
        process = subprocess.Popen(command)
    return browser_locate, process


async def run_browser_agent(
    question,
    base_url,
    api_key,
    model_name,
    temperature,
    enable_memory,
    browser_port,
    browser_locate,
    headless,
    extract_base_url,
    extract_api_key,
    extract_model_name,
    extract_temperature,
    exclude_actions,
    window_width,
    window_height,
    highlight_elements,
    add_interactive_elements,
    system_message_file_name,
    max_steps,
    use_inner_chrome,
    google_api_key,
    google_search_engine_id,
    in_docker,
):
    controller = Controller(
        output_model=Answer,
        exclude_actions=exclude_actions,
    )
    if use_inner_chrome:
        browser = Browser(
            config=BrowserConfig(
                # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
                new_context_config=BrowserContextConfig(
                    no_viewport = False,
                    window_width = window_width,
                    window_height = window_height,
                    highlight_elements = highlight_elements,
                    google_api_key = google_api_key,
                    google_search_engine_id = google_search_engine_id,
                ),
                headless=headless,
                in_docker=in_docker,
            )
        )
    else:
        browser = Browser(
            config=BrowserConfig(
                # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
                browser_binary_path=browser_locate,
                chrome_remote_debugging_port=browser_port,
                new_context_config=BrowserContextConfig(
                    no_viewport = False,
                    window_width = window_width,
                    window_height = window_height,
                    highlight_elements = highlight_elements,
                    google_api_key = google_api_key,
                    google_search_engine_id = google_search_engine_id,
                ),
                headless=headless,
            )
        )
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )
    page_extraction_llm = ChatOpenAI(
        model=extract_model_name,
        api_key=extract_api_key,
        base_url=extract_base_url,
        temperature=extract_temperature,
    )

    # depracated from browser_use >= 0.4.5
    memory_config=None
    if enable_memory:
        memory_config=MemoryConfig( # Ensure llm_instance is passed if not using default LLM config
            llm_instance=page_extraction_llm,      # Important: Pass the agent's LLM instance here
            agent_id="browser_agent_01",
            memory_interval=10,
        )

    task = question
    agent = Agent(
        task=task,
        llm=llm,
        page_extraction_llm=page_extraction_llm,
        # browser_session=browser_session,
        browser=browser,
        controller=controller,
        tool_calling_method="raw",
        memory_config=memory_config,
        enable_memory=enable_memory,
        add_interactive_elements=add_interactive_elements,
        system_message_file_name=system_message_file_name,
    )

    history = None
    try:
        history = await agent.run(max_steps=max_steps)
    except Exception as e:
        print(e)
    finally:
        await browser.close()
    return history

async def process_browser_request(
    browser_request: BrowserAgentRequest, request_id: str = Depends(get_request_id)
):
    async with browser_semaphore: 
        logger.info(f"!!!Semaphore value = {browser_semaphore._value}")
        try:
            logger.info(f"[{request_id}] Processing browser agentic search")

            question = browser_request.question
            base_url = browser_request.base_url
            api_key = browser_request.api_key
            model_name = browser_request.model_name
            temperature = browser_request.temperature
            enable_memory = browser_request.temperature
            browser_port = browser_request.browser_port
            user_data_dir = browser_request.user_data_dir
            headless = browser_request.headless
            window_width = browser_request.window_width
            window_height = browser_request.window_height
            extract_base_url = browser_request.extract_base_url
            extract_api_key = browser_request.extract_api_key
            extract_model_name = browser_request.extract_model_name
            extract_temperature = browser_request.extract_temperature
            return_trace = browser_request.return_trace
            save_trace = browser_request.save_trace
            oss_access_key_id = browser_request.oss_access_key_id
            oss_access_key_secret = browser_request.oss_access_key_secret
            oss_endpoint = browser_request.oss_endpoint
            oss_bucket_name = browser_request.oss_bucket_name
            trace_dir_name = browser_request.trace_dir_name
            trace_file_name = browser_request.trace_file_name
            max_steps = browser_request.max_steps
            mode = browser_request.mode
            use_inner_chrome = browser_request.use_inner_chrome
            google_api_key = browser_request.google_api_key
            google_search_engine_id = browser_request.google_search_engine_id   
            in_docker = browser_request.in_docker

            if mode == ModeEnum.SOM:
                exclude_actions = [  
                    "search_google",
                    "search_bing",
                    "search_baidu",
                    "goto",
                    "click",
                    "type",
                    "scroll",
                    "back",
                    "finish",
                ]
                highlight_elements = True
                add_interactive_elements = True
                system_message_file_name = "system_prompt.md"
            else:
                exclude_actions = [   
                    "search_google",
                    "search_bing",
                    "search_baidu",
                    # "search_yahoo",
                    # "search_duckduckgo",
                    "go_to_url",
                    "go_back",
                    "click_element_by_index",
                    "input_text",
                    "save_pdf",
                    # "switch_tab",
                    # "open_tab",
                    # "close_tab",
                    "extract_content",
                    "scroll_down",
                    "scroll_up",
                    "send_keys",
                    "scroll_to_text",
                    "get_dropdown_options",
                    "select_dropdown_option",
                    "drag_drop",
                    "get_sheet_contents",
                    "select_cell_or_range",
                    "get_range_contents",
                    "clear_selected_range",
                    "input_selected_cell_text",
                    "update_range_contents",
                    "finish",
                ]
                highlight_elements = False
                add_interactive_elements = False
                system_message_file_name = "system_prompt_vision.md"

            answer_dict_li,trace_dict_li,oss_res_li=[],[],[]
            for a_question,a_trace_file_name in zip(question,trace_file_name):
                try:
                    if not use_inner_chrome:
                        browser_locate, chrome_process = run_chrome_debug_mode(browser_port, user_data_dir, headless)
                    else:
                        browser_locate, chrome_process = None, None
            
                    agent_history = await run_browser_agent(
                        a_question,
                        base_url,
                        api_key,
                        model_name,
                        temperature,
                        enable_memory,
                        browser_port,
                        browser_locate,
                        headless,
                        extract_base_url,
                        extract_api_key,
                        extract_model_name,
                        extract_temperature,
                        exclude_actions,
                        window_width,
                        window_height,
                        highlight_elements,
                        add_interactive_elements,
                        system_message_file_name,
                        max_steps,
                        use_inner_chrome,
                        google_api_key,
                        google_search_engine_id,
                        in_docker,
                    )

                    if not use_inner_chrome:
                        chrome_process.terminate()
                    
                    if agent_history:
                        result = agent_history.final_result()
                        parsed_res: Answer = Answer.model_validate_json(result)
                        answer_dict = parsed_res.model_dump()
                        print("\n--------------------------------")
                        print(f"answer_dict: {answer_dict}")
                        print("\n--------------------------------")
                        answer_dict_li.append(answer_dict)

                    tarce_info_dict = {"question": question, "agent_answer": answer_dict}
                    if return_trace:
                        trace_dict = get_a_trace_with_img(agent_history, tarce_info_dict)
                        trace_dict_li.append(trace_dict)

                    oss_res = {"success": False}
                    if save_trace:
                        oss_client=get_oss_client(oss_access_key_id, oss_access_key_secret, oss_endpoint, oss_bucket_name, True)
                        if oss_client._initialized:
                            save_path=save_trace_in_oss(agent_history, tarce_info_dict, oss_client, trace_dir_name, a_trace_file_name)
                            oss_res["success"] = True if save_path else False
                            oss_res["path"] = save_path
                        logger.info(f"oss_res: {oss_res}")
                    oss_res_li.append(oss_res)
                    
                    
                except Exception as e:
                    print(e)
                    if not use_inner_chrome and chrome_process:
                        chrome_process.terminate()
            return {"answer_dict_li": answer_dict_li, "trace_dict_li": trace_dict_li, "oss_res_li": oss_res_li}
            
        except Exception as e:
            logger.error(f"[{request_id}] Error processing browser agentic search: {e}")


@browser_router.post("/browser_use_background")
async def agentic_browser_background_endpoint(
    background_tasks: BackgroundTasks,browser_request: BrowserAgentRequest, request_id: str = Depends(get_request_id)
):
    background_tasks.add_task(process_browser_request, browser_request,request_id)
    return {"message": "Request received and processing in background", "request_id": request_id,"pod_name":os.getenv('POD_NAME')}


@browser_router.post("/browser_use")
async def agentic_browser_endpoint(
    browser_request: BrowserAgentRequest, request_id: str = Depends(get_request_id)
):
    """Advanced search endpoint using browser agent.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "model_name": "your_model_name",
        "browser_port": "the_browser_port",  // optional
        "temperature": 0.3,  // optional
        "enable_memory": false,  // optional
        "user_data_dir": "/tmp/chrome-debug/0000"  // optional
    }
    """
    try:
        res_dict = await process_browser_request(browser_request, request_id)
        # logger.info(f"[{request_id}] Processing browser agentic search")

        # question = browser_request.question
        # base_url = browser_request.base_url
        # api_key = browser_request.api_key
        # model_name = browser_request.model_name
        # temperature = browser_request.temperature
        # enable_memory = browser_request.temperature
        # browser_port = browser_request.browser_port
        # user_data_dir = browser_request.user_data_dir
        # headless = browser_request.headless
        # window_width = browser_request.window_width
        # window_height = browser_request.window_height
        # extract_base_url = browser_request.extract_base_url
        # extract_api_key = browser_request.extract_api_key
        # extract_model_name = browser_request.extract_model_name
        # extract_temperature = browser_request.extract_temperature
        # return_trace = browser_request.return_trace
        # save_trace = browser_request.save_trace
        # oss_access_key_id = browser_request.oss_access_key_id
        # oss_access_key_secret = browser_request.oss_access_key_secret
        # oss_endpoint = browser_request.oss_endpoint
        # oss_bucket_name = browser_request.oss_bucket_name
        # trace_dir_name = browser_request.trace_dir_name
        # trace_file_name = browser_request.trace_file_name
        # max_steps = browser_request.max_steps
        # mode = browser_request.mode
        # use_inner_chrome = browser_request.use_inner_chrome
        # google_api_key = browser_request.google_api_key
        # google_search_engine_id = browser_request.google_search_engine_id
        # in_docker = browser_request.in_docker

        # if mode == ModeEnum.SOM:
        #     exclude_actions = [  
        #         "search_google",
        #         "search_bing",
        #         "search_baidu",
        #         "goto",
        #         "click",
        #         "type",
        #         "scroll",
        #         "back",
        #         "finish",
        #     ]
        #     highlight_elements = True
        #     add_interactive_elements = True
        #     system_message_file_name = "system_prompt.md"
        # else:
        #     exclude_actions = [   
        #         "search_google",
        #         "search_bing",
        #         "search_baidu",
        #         "search_yahoo",
        #         "search_duckduckgo",
        #         "go_to_url",
        #         "go_back",
        #         "click_element_by_index",
        #         "input_text",
        #         "save_pdf",
        #         "switch_tab",
        #         "open_tab",
        #         "close_tab",
        #         "extract_content",
        #         "scroll_down",
        #         "scroll_up",
        #         "send_keys",
        #         "scroll_to_text",
        #         "get_dropdown_options",
        #         "select_dropdown_option",
        #         "drag_drop",
        #         "get_sheet_contents",
        #         "select_cell_or_range",
        #         "get_range_contents",
        #         "clear_selected_range",
        #         "input_selected_cell_text",
        #         "update_range_contents",
        #         "finish",
        #     ]
        #     highlight_elements = False
        #     add_interactive_elements = False
        #     system_message_file_name = "system_prompt_vision.md"

        # answer_dict_li,trace_dict_li,oss_res_li=[],[],[]
        # for a_question,a_trace_file_name in zip(question,trace_file_name):
        #     try:
        #         if not use_inner_chrome:
        #             browser_locate, chrome_process = run_chrome_debug_mode(browser_port, user_data_dir, headless)
        #         else:
        #             browser_locate, chrome_process = None, None

        #         agent_history = await run_browser_agent(
        #             a_question,
        #             base_url,
        #             api_key,
        #             model_name,
        #             temperature,
        #             enable_memory,
        #             browser_port,
        #             browser_locate,
        #             headless,
        #             extract_base_url,
        #             extract_api_key,
        #             extract_model_name,
        #             extract_temperature,
        #             exclude_actions,
        #             window_width,
        #             window_height,
        #             highlight_elements,
        #             add_interactive_elements,
        #             system_message_file_name,
        #             max_steps,
        #             use_inner_chrome,
        #             google_api_key,
        #             google_search_engine_id,
        #             in_docker,
        #         )
        #         if not use_inner_chrome:
        #             chrome_process.terminate()
                
        #         if agent_history:
        #             result = agent_history.final_result()
        #             parsed_res: Answer = Answer.model_validate_json(result)
        #             answer_dict = parsed_res.model_dump()
        #             print("\n--------------------------------")
        #             print(f"answer_dict: {answer_dict}")
        #             print("\n--------------------------------")
        #             answer_dict_li.append(answer_dict)

        #         tarce_info_dict = {"question": question, "agent_answer": answer_dict}
        #         if return_trace:
        #             trace_dict = get_a_trace_with_img(agent_history, tarce_info_dict)
        #             trace_dict_li.append(trace_dict)
                
        #         oss_res = {"success": False}
        #         if save_trace:
        #             oss_client=get_oss_client(oss_access_key_id, oss_access_key_secret, oss_endpoint, oss_bucket_name, True)
        #             if oss_client._initialized:
        #                 save_path=save_trace_in_oss(agent_history, tarce_info_dict, oss_client, trace_dir_name, a_trace_file_name)
        #                 oss_res["success"] = True if save_path else False
        #                 oss_res["path"] = save_path
        #             logger.info(f"oss_res: {oss_res}")
        #         oss_res_li.append(oss_res)

        #     except Exception as e:
        #         print(e)
        #         if not use_inner_chrome and chrome_process:
        #             chrome_process.terminate()
        

        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "pod_name":os.getenv('POD_NAME'),
            "question": browser_request.question,
            "results": json.dumps(res_dict["answer_dict_li"], ensure_ascii=False),
            "trace": json.dumps(res_dict["trace_dict_li"], ensure_ascii=False) if browser_request.return_trace else "{}",
            "oss_res": json.dumps(res_dict["oss_res_li"], ensure_ascii=False) if browser_request.save_trace else "{}",
        }

        return response_data

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@browser_router.post("/browser_get_trace")
async def get_browser_trace_endpoint(
    browser_request: GetBrowserTraceRequest, request_id: str = Depends(get_request_id)
):
    """Advanced search endpoint using browser agent.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "model_name": "your_model_name",
        "browser_port": "the_browser_port",  // optional
        "temperature": 0.3,  // optional
        "enable_memory": false,  // optional
        "user_data_dir": "/tmp/chrome-debug/0000"  // optional
    }
    """
    try:
        logger.info(f"[{request_id}] Processing browser agentic search")

        
        oss_access_key_id = browser_request.oss_access_key_id
        oss_access_key_secret = browser_request.oss_access_key_secret
        oss_endpoint = browser_request.oss_endpoint
        oss_bucket_name = browser_request.oss_bucket_name
        trace_file_dir = browser_request.trace_file_dir
        trace_file_name_li = browser_request.trace_file_name_li

        oss_res={"success": False}
        oss_client=get_oss_client(oss_access_key_id, oss_access_key_secret, oss_endpoint, oss_bucket_name, True)
        if oss_client._initialized and trace_file_dir!="":
            if len(trace_file_name_li)==0:
                trace_li=list_traces(oss_client,trace_file_dir)
            else:
                trace_li=trace_file_name_li
            trace_data=get_traces_from_oss(oss_client,trace_file_dir,trace_li)
            oss_res["success"] = True
            oss_res["trace_data"] = trace_data
        if trace_file_dir=="":
            oss_res["reason"] = "trace_file_dir is not given"
        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "pod_name":os.getenv('POD_NAME'),
            "oss_res": json.dumps(oss_res, ensure_ascii=False),
        }

        return response_data

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@browser_router.post("/browser_list_trace")
async def list_browser_trace_dir_endpoint(
    browser_request: ListBrowserTraceDirRequest, request_id: str = Depends(get_request_id)
):
    """Advanced search endpoint using browser agent.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "model_name": "your_model_name",
        "browser_port": "the_browser_port",  // optional
        "temperature": 0.3,  // optional
        "enable_memory": false,  // optional
        "user_data_dir": "/tmp/chrome-debug/0000"  // optional
    }
    """
    try:
        logger.info(f"[{request_id}] Processing browser agentic search")

        
        oss_access_key_id = browser_request.oss_access_key_id
        oss_access_key_secret = browser_request.oss_access_key_secret
        oss_endpoint = browser_request.oss_endpoint
        oss_bucket_name = browser_request.oss_bucket_name
        trace_file_dir = browser_request.trace_file_dir

        oss_res = {"success": False}
        oss_client=get_oss_client(oss_access_key_id, oss_access_key_secret, oss_endpoint, oss_bucket_name, True)
        if oss_client._initialized and trace_file_dir!="":
            trace_li=list_traces(oss_client, trace_file_dir)
            oss_res["success"] = True
            oss_res["trace_li"] = trace_li
        if trace_file_dir=="":
            oss_res["reason"] = "trace_file_dir is not given"

        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "pod_name":os.getenv('POD_NAME'),
            "oss_res": json.dumps(oss_res, ensure_ascii=False),
        }

        return response_data

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    

@browser_router.post("/browser_if_trace_exist")
async def browser_trace_exist_endpoint(
    browser_request: BrowserTraceExistRequest, request_id: str = Depends(get_request_id)
):
    """Advanced search endpoint using browser agent.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "your_openai_base_url",
        "api_key": "your_openai_api_key",
        "model_name": "your_model_name",
        "browser_port": "the_browser_port",  // optional
        "temperature": 0.3,  // optional
        "enable_memory": false,  // optional
        "user_data_dir": "/tmp/chrome-debug/0000"  // optional
    }
    """
    try:
        logger.info(f"[{request_id}] Processing browser agentic search")

        
        oss_access_key_id = browser_request.oss_access_key_id
        oss_access_key_secret = browser_request.oss_access_key_secret
        oss_endpoint = browser_request.oss_endpoint
        oss_bucket_name = browser_request.oss_bucket_name
        trace_file_dir = browser_request.trace_file_dir
        trace_file_name = browser_request.trace_file_name
        
        trace_prefix="ml001/browser_agent/traces/"
        file_path=os.path.join(trace_prefix,trace_file_dir,trace_file_name+".json")
        oss_res = {"exist": False,"file":file_path}
        oss_client=get_oss_client(oss_access_key_id, oss_access_key_secret, oss_endpoint, oss_bucket_name, True)
        if oss_client.exists(file_path):
            oss_res["exist"] = True

        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "pod_name":os.getenv('POD_NAME'),
            "oss_res": json.dumps(oss_res, ensure_ascii=False),
        }

        return response_data

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")