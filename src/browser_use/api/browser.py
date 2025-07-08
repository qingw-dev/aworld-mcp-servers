"""Health check API routes."""
import asyncio
from datetime import datetime
from flask import Blueprint, jsonify
import uuid
from flask import Blueprint, request, jsonify, g
from pydantic import ValidationError
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig
import subprocess
from pydantic import BaseModel

from ...logging import get_logger
from ...metrics import get_metrics_collector

logger = get_logger(__name__)
metrics_collector = get_metrics_collector()


browser_bp = Blueprint("browser", __name__, url_prefix="/browser")


class Answer(BaseModel):
    important_records: str
    final_answer: str

async def run_browser_agent(question,browser_port,user_data_dir,model_name,api_key,base_url,temperature,enable_memory):
    controller = Controller(output_model=Answer)
    command = [
        # "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port="+browser_port,
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir="+user_data_dir,
        "--headless",  # 启用无头模式
        # "--disable-gpu",  # 禁用 GPU 加速（可选）
        # "--window-size=1920,1080"  # 设置窗口大小（可选）
    ]
    process = subprocess.Popen(command)

    browser = Browser(
        config=BrowserConfig(
            # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
            browser_binary_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            # browser_binary_path="/usr/bin/google-chrome",
            chrome_remote_debugging_port=browser_port,
            new_context_config=BrowserContextConfig(no_viewport=False),
            headless=True,
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


@browser_bp.route("/agentic", methods=["POST"])
@metrics_collector.log_performance
def agentic_search_endpoint():
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
        return jsonify(response_data)
        
    except ValidationError as e:
        raise e  # Will be handled by the error handler
    except Exception as e:
        logger.error(f"[{g.request_id}] Error in agentic search endpoint: {e}")
        raise e  # Will be handled by the error handler