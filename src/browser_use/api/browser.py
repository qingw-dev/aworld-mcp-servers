"""Health check API routes."""
import asyncio
from datetime import datetime
from browser_use.agent.memory.views import MemoryConfig
from flask import Blueprint, jsonify
import uuid
from flask import Blueprint, request, jsonify, g
from pydantic import ValidationError
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig
import subprocess
from pydantic import BaseModel
import json

from ...server_logging import get_logger
from ...metrics import get_metrics_collector
from ..utils import get_a_trace_with_img


logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


browser_bp = Blueprint("browser", __name__, url_prefix="/browser")

@browser_bp.before_request
def add_request_id():
    """Add unique request ID to each search request."""
    g.request_id = str(uuid.uuid4())[:8]
    

class Answer(BaseModel):
    important_records: str
    final_answer: str

def run_chrome_debug_mode(browser_port,user_data_dir,headless):
    browser_locate="/usr/bin/google-chrome"
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
        browser_locate="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
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

async def run_browser_agent(question,base_url,api_key,model_name,temperature,enable_memory,browser_port,browser_locate,headless,extract_base_url,extract_api_key,extract_model_name,extract_temperature):
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
    llm=ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )
    page_extraction_llm=ChatOpenAI(
        model=extract_model_name,
        api_key=extract_api_key,
        base_url=extract_base_url,
        temperature=extract_temperature,
    )
    memory_config=None
    if enable_memory:
        memory_config=MemoryConfig( # Ensure llm_instance is passed if not using default LLM config
            llm_instance=page_extraction_llm,      # Important: Pass the agent's LLM instance here
            agent_id="browser_agent_01",
            memory_interval=10,
        )

    task=question
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
    )

    history=None
    try:
        history = await agent.run()
    except Exception as e:
        print(e)
    finally:
        await browser.close()
    return history
    


@browser_bp.route("/browser_use", methods=["POST"])
@metrics_collector.log_performance
def agentic_search_endpoint():
    """Advanced search endpoint using handle_single_query function.

    Expected JSON payload:
    {
        "question": "user question",
        "base_url": "openai_base_url for browser agent",
        "api_key": "openai_api_key for browser agent",
        "model_name": "model_name for browser agent",
        "temperature": "the temperature for browser agent LLM, default is 0.3",
        "enable_memory": "whether to enable memory, default is False",
        "browser_port": "the browser port, default is 9111",
        "user_data_dir": "the user_data_dir for browser, default is /tmp/chrome-debug/0000",
        "headless": "whether to run browser in headless mode, default is True",
        "extract_base_url": "the extract_base_url for extract tool, default same as base_url",
        "extract_api_key": "the extract_api_key for extract tool, default same as api_key",
        "extract_model_name": "the extract_model_name for extract tool, default same as model_name",
        "extract_temperature": "the extract_temperature for extract tool, default is 0.3",
        "return_trace": "whether to return trace, default is False",
        "save_trace": "whether to save trace, default is True",
    }
    """

    try:
        if not request.is_json:
            logger.warning(f"[{g.request_id}] Non-JSON request received")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        required_fields = ["question", "base_url", "api_key", "model_name"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"[{g.request_id}] Missing required field: '{field}'")
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        question = data["question"]
        base_url = data["base_url"]
        api_key = data["api_key"]
        model_name = data["model_name"]
        temperature = data.get("temperature", 0.3)
        enable_memory = data.get("enable_memory", False)
        browser_port = data.get("browser_port","9111")
        user_data_dir = data.get("user_data_dir", "/tmp/chrome-debug/0000")
        headless = data.get("headless", True)
        extract_base_url = data.get("extract_base_url", base_url)
        extract_api_key = data.get("extract_api_key", api_key)
        extract_model_name = data.get("extract_model_name", model_name)
        extract_temperature = data.get("extract_temperature", 0.3)
        return_trace = data.get("return_trace", False)
        save_trace = data.get("save_trace", True)

        browser_locate, chrome_process=run_chrome_debug_mode(browser_port,user_data_dir,headless)
        agent_history=asyncio.run(run_browser_agent(question,base_url,api_key,model_name,temperature,enable_memory,browser_port,browser_locate,headless,extract_base_url,extract_api_key,extract_model_name,extract_temperature))
        chrome_process.terminate()

        if agent_history:
            result = agent_history.final_result()
            parsed_res: Answer = Answer.model_validate_json(result)
            answer_dict = parsed_res.model_dump()
            print('\n--------------------------------')
            print(f'answer_dict: {answer_dict}')
            print('\n--------------------------------')

        if return_trace:
            tarce_info_dict={
                "question": question,
                "agent_answer": answer_dict
            }
            trace_dict = get_a_trace_with_img(agent_history,tarce_info_dict)

        
        # Convert to dict for JSON response
        response_data = {
            "request_id": g.request_id,
            "question": question,
            "results": json.dumps(answer_dict, ensure_ascii=False),
            "trace": json.dumps(trace_dict,ensure_ascii=False) if return_trace else "{}"
        }

        logger.info(f"[{g.request_id}] Browser Agent completed successfully")
        return jsonify(response_data), 200
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in Browser Agent endpoint: {e}")
        raise e  # Will be handled by the error handler