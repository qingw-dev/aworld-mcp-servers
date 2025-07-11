# aworld-mcp-servers
The accompanying repository for the [AWorld](https://github.com/inclusionAI/AWorld) project.

- 🦩 [2025/06/19] AWorld has achieved 72.43 on the GAIA test. The #1 open-source project—and the only one in GAIA's top 10. [🐦 tweets](https://x.com/gujinjie/status/1938265242955305319)

# API Integration and Testing

This repository contains examples of API requests and testing for various services, including health checks, web scraping with [Google API](https://developers.google.com/custom-search/v1/introduction) and BeautifulSoup, and [DeepResearcher](https://github.com/GAIR-NLP/DeepResearcher) search workflow re-implementation.

## Quick Setup

### Prerequisites
- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Install uv** (if not already installed):
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Or via pip
   pip install uv
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/aworld-mcp-servers.git
   cd aworld-mcp-servers
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   ```

4. **Activate the virtual environment** (optional, uv handles this automatically):
   ```bash
   source .venv/bin/activate  # macOS/Linux
   # or
   .venv\Scripts\activate     # Windows
   ```

### Running the Application

- **Main Flask server**:
  ```bash
  uv run aworld-server
  ```

- **FastAPI server**:
  ```bash
  uv run aworld-fastapi
  ```

- **GAIA runner**:
  ```bash
  uv run gaia-runner
  ```

- **Run as module** (alternative):
  ```bash
  uv run python -m src.main
  ```

### Development Setup

1. **Install development dependencies**:
   ```bash
   uv sync --dev
   ```

2. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

3. **Run tests**:
   ```bash
   uv run pytest
   ```

4. **Code formatting and linting**:
   ```bash
   uv run black .
   uv run ruff check .
   uv run mypy src/
   ```

## Table of Contents
- [Health Check](#health-check)
- [Google API + BeautifulSoup](#google-api--beautifulsoup)
- [Deep Researcher](#deep-researcher)
- [OpenRouter API](#openrouter-api)
- [Browser Use API](#browser-use-api)

## Health Check
This section demonstrates how to perform a health check on a specific service endpoint.

```bash
curl -X GET http://DEPLOYED_HOST:PORT/health
```

### Notes
- The health check endpoint is used to verify the availability and connectivity of the service.
- If the request fails, it may indicate that the service is down or there is a network issue.

## Google API + BeautifulSoup
This section shows how to use the Google API and BeautifulSoup to scrape web pages.

```bash
curl -X POST http://DEPLOYED_HOST:PORT/search \
     -H "Content-Type: application/json" \
     -d '{
             "api_key": "YOUR_GOOGLE_API_KEY",
             "cse_id": "YOUR_GOOGLE_CSE_ID",
             "queries": ["machine learning"],
             "num_results": 5,
             "fetch_content": true,
             "language": "en",
             "country": "US",
             "safe_search": true,
             "max_len": 8192 # optional, max length of the content to fetch, only works when fetch_content is true
         }'
```

### Notes
- Replace `YOUR_GOOGLE_API_KEY` and `YOUR_GOOGLE_CSE_ID` with your actual [Google API](https://developers.google.com/custom-search/v1/introduction) key and Custom Search Engine (CSE) ID.
- This request searches for web pages related to "machine learning" and fetches the content of the top 5 results.

## Deep Researcher
This section demonstrates how to perform a deep research query using [Serper API](https://serper.dev).

```bash
curl -X POST http://DEPLOYED_HOST:PORT/search/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "question": "machine learning",
    "search_queries": ["machine learning"],
    "base_url": "YOUR_LLM_ENDPOINT",
    "api_key": "YOUR_API_KEY",
    "llm_model_name": "qwen/qwen-plus",
    "serper_api_key": "YOUR_SERPER_API_KEY",
    "topk": 5
  }'
```

### Notes
- Replace `YOUR_LLM_ENDPOINT`, `YOUR_API_KEY` and `YOUR_SERPER_API_KEY` with your actual API keys.
- The `base_url` is the endpoint for the deep research service.
- This request searches for information related to "machine learning" and returns the top 5 results.

## OpenRouter API
This section demonstrates how to use the OpenRouter API for LLM chat completions and model listing.
### Chat Completions
```bash
curl -X POST http://DEPLOYED_HOST:PORT/openrouter/completions \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "YOUR_OPENROUTER_API_KEY",
    "model": "google/gemini-2.5-pro",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      }
    ],
    "site_url": "https://your-site.com",
    "site_name": "Your Site Name"
  }'
```

### List Available Models
```bash
curl -X GET http://DEPLOYED_HOST:PORT/openrouter/models
```

### Notes
- Replace `YOUR_OPENROUTER_API_KEY` with your actual [OpenRouter](https://openrouter.ai) API key.
- The `model` parameter supports various models available through OpenRouter (e.g., "google/gemini-2.5-pro", "anthropic/claude-opus-4", "openai/gpt-4").
- `site_url` and `site_name` are optional parameters for tracking and attribution.

## Browser Use API
This section demonstrates how to use the Browser Use API for automated web browsing tasks.

```bash
curl -X POST http://DEPLOYED_HOST:PORT/browser_use \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Go to google.com and search for machine learning",
    "base_url": "YOUR_LLM_ENDPOINT",
    "api_key": "YOUR_API_KEY",
    "model_name": "gpt-4o",
    "temperature": 0.3,
    "enable_memory": false,
    "browser_port": "9111",
    "user_data_dir": "/tmp/chrome-debug/0000",
    "headless": true,
    "extract_base_url": "YOUR_LLM_ENDPOINT",
    "extract_api_key": "YOUR_API_KEY",
    "extract_model_name": "gpt-4o",
    "extract_temperature": 0.3,
    "return_trace": false
  }'
```

### Notes
- Replace `YOUR_LLM_ENDPOINT` and `YOUR_API_KEY` with your actual LLM service endpoint and API key.
- The `question` parameter should contain natural language instructions for the browser automation task.
- `model_name` supports various models (e.g., "gpt-4o", "claude-3-opus-20240229", "gemini-pro").
- Set `headless` to `false` if you want to see the browser window during automation.
- `enable_memory` allows the agent to remember previous interactions.
- `return_trace` includes detailed execution trace in the response.

## License
This repository is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
