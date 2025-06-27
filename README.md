# aworld-mcp-servers
The accompanying repository for the [AWorld](https://github.com/inclusionAI/AWorld) project.

- 🦩 [2025/06/19] AWorld has achieved 72.43 on the GAIA test. The #1 open-source project—and the only one in GAIA's top 10. [🐦 tweets]((https://x.com/gujinjie/status/1938265242955305319))

# API Integration and Testing

This repository contains examples of API requests and testing for various services, including health checks, web scraping with [Google API](https://developers.google.com/custom-search/v1/introduction) and BeautifulSoup, and [DeepResearcher](https://github.com/GAIR-NLP/DeepResearcher) search workflow re-implementation.

## Table of Contents
- [Health Check](#health-check)
- [Google API + BeautifulSoup](#google-api--beautifulsoup)
- [Deep Researcher](#deep-researcher)

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
             "safe_search": true
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
    "serper_api_key": "YOUR_SERPER_API_KEY",
    "topk": 5
  }'
```

### Notes
- Replace `YOUR_LLM_ENDPOINT`, `YOUR_API_KEY` and `YOUR_SERPER_API_KEY` with your actual API keys.
- The `base_url` is the endpoint for the deep research service.
- This request searches for information related to "machine learning" and returns the top 5 results.

## License
This repository is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.