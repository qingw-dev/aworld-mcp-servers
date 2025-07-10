"""FastAPI Browser Use API routes."""

import json
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContextConfig

from ...metrics import get_metrics_collector
from ...server_logging import get_logger
from ..utils import get_a_trace_with_img

browser_router = APIRouter(prefix="/browser", tags=["browser"])
logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


class Answer(BaseModel):
    important_records: str
    final_answer: str


class BrowserAgentRequest(BaseModel):
    question: str
    base_url: str
    api_key: str
    model_name: str
    temperature: float = 0.3
    enable_memory: bool = False
    browser_port: str = "9111"
    user_data_dir: str = "/tmp/chrome-debug/0000"
    headless: bool = True
    extract_base_url: str = ""
    extract_api_key: str = ""
    extract_model_name: str = ""
    extract_temperature: float = 0.3
    return_trace: bool = False
    save_trace: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.extract_base_url == "":
            self.extract_base_url = self.base_url
        if self.extract_api_key == "":
            self.extract_api_key = self.api_key
        if self.extract_model_name == "":
            self.extract_model_name = self.model_name


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
):
    controller = Controller(output_model=Answer)
    browser = Browser(
        config=BrowserConfig(
            # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
            browser_binary_path=browser_locate,
            chrome_remote_debugging_port=browser_port,
            new_context_config=BrowserContextConfig(no_viewport=False),
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
    # memory_config=None
    # if enable_memory:
    #     memory_config=MemoryConfig( # Ensure llm_instance is passed if not using default LLM config
    #         llm_instance=page_extraction_llm,      # Important: Pass the agent's LLM instance here
    #         agent_id="browser_agent_01",
    #         memory_interval=10,
    #     )

    task = question
    agent = Agent(
        task=task,
        llm=llm,
        page_extraction_llm=page_extraction_llm,
        # browser_session=browser_session,
        browser=browser,
        controller=controller,
        tool_calling_method="raw",
        # memory_config=memory_config,
        # enable_memory=enable_memory,
    )

    history = None
    try:
        history = await agent.run()
    except Exception as e:
        print(e)
    finally:
        await browser.close()
    return history


@browser_router.post("/browser_use")
async def agentic_browser_endpoint(
    browser_request: BrowserAgentRequest, request: Request, request_id: str = Depends(get_request_id)
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

        question = browser_request.question
        base_url = browser_request.base_url
        api_key = browser_request.api_key
        model_name = browser_request.model_name
        temperature = browser_request.temperature
        enable_memory = browser_request.temperature
        browser_port = browser_request.browser_port
        user_data_dir = browser_request.user_data_dir
        headless = browser_request.headless
        extract_base_url = browser_request.extract_base_url
        extract_api_key = browser_request.extract_api_key
        extract_model_name = browser_request.extract_model_name
        extract_temperature = browser_request.extract_temperature
        return_trace = browser_request.return_trace
        save_trace = browser_request.save_trace

        browser_locate, chrome_process = run_chrome_debug_mode(browser_port, user_data_dir, headless)
        agent_history = await run_browser_agent(
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
        )
        chrome_process.terminate()

        if agent_history:
            result = agent_history.final_result()
            parsed_res: Answer = Answer.model_validate_json(result)
            answer_dict = parsed_res.model_dump()
            print("\n--------------------------------")
            print(f"answer_dict: {answer_dict}")
            print("\n--------------------------------")

        if return_trace:
            tarce_info_dict = {"question": question, "agent_answer": answer_dict}
            trace_dict = get_a_trace_with_img(agent_history, tarce_info_dict)

        # Convert to dict for JSON response
        response_data = {
            "request_id": request_id,
            "question": question,
            "results": json.dumps(answer_dict, ensure_ascii=False),
            "trace": json.dumps(trace_dict, ensure_ascii=False) if return_trace else "{}",
        }

        return response_data

    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
