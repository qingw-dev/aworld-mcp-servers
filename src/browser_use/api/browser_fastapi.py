"""FastAPI Browser Use API routes."""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, ValidationError
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig
import subprocess

from ...server_logging import get_logger
from ...metrics import get_metrics_collector

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
    browser_port: str = "9111"
    temperature: float = 0.3
    enable_memory: bool = False
    user_data_dir: str = "/tmp/chrome-debug/0000"


def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, 'request_id', 'unknown')


async def run_browser_agent(
    question: str,
    browser_port: str,
    user_data_dir: str,
    model_name: str,
    api_key: str,
    base_url: str,
    temperature: float,
    enable_memory: bool
) -> Answer | None:
    """Run browser agent with given parameters."""
    controller = Controller(output_model=Answer)
    command = [
        "/usr/bin/google-chrome",
        f"--remote-debugging-port={browser_port}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={user_data_dir}",
        "--headless",
    ]
    process = subprocess.Popen(command)

    browser = Browser(
        config=BrowserConfig(
            browser_binary_path="/usr/bin/google-chrome",
            chrome_remote_debugging_port=browser_port,
            new_context_config=BrowserContextConfig(no_viewport=False),
            headless=True,
        )
    )
    
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )
    
    page_extraction_llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )

    agent = Agent(
        task=question,
        llm=llm,
        page_extraction_llm=page_extraction_llm,
        browser=browser,
        controller=controller,
        tool_calling_method="raw",
        enable_memory=enable_memory,
    )

    parsed = None
    try:
        history = await agent.run()
        result = history.final_result()
        parsed = Answer.model_validate_json(result)
    except Exception as e:
        logger.error(f"Browser agent error: {e}")
    finally:
        await browser.close()
        process.terminate()
        return parsed


@browser_router.post("/agentic")
async def agentic_search_endpoint(
    browser_request: BrowserAgentRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
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
        
        parsed = await run_browser_agent(
            question=browser_request.question,
            browser_port=browser_request.browser_port,
            user_data_dir=browser_request.user_data_dir,
            model_name=browser_request.model_name,
            api_key=browser_request.api_key,
            base_url=browser_request.base_url,
            temperature=browser_request.temperature,
            enable_memory=browser_request.enable_memory
        )

        results = {}
        if parsed:
            logger.info(f"[{request_id}] Browser agent completed successfully")
            results = {
                "important_records": parsed.important_records,
                "final_answer": parsed.final_answer
            }
        else:
            logger.warning(f"[{request_id}] Browser agent returned no results")

        response_data = {
            "request_id": request_id,
            "question": browser_request.question,
            "results": results,
        }

        return response_data
        
    except ValidationError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Error in browser agentic search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")