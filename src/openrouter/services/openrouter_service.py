"""OpenRouter API service for handling external API calls."""

import json
import time
from typing import Dict, Any, Tuple

import requests

from ..models.requests import ChatCompletionRequest
from ..models.responses import ChatCompletionResponse, ModelsResponse
from ...server_logging import get_logger
from ...metrics import get_metrics_collector


class OpenRouterService:
    """Service for interacting with OpenRouter API."""
    
    def __init__(self) -> None:
        """Initialize the OpenRouter service."""
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.base_url = "https://openrouter.ai/api/v1"
        self.timeout = 30
    
    def chat_completion(
        self,
        request: ChatCompletionRequest,
        request_id: str
    ) -> Tuple[ChatCompletionResponse, bool]:
        """Perform a chat completion request.
        
        Args:
            request: The chat completion request
            request_id: Request ID for logging
            
        Returns:
            Tuple of (response, success status)
        """
        start_time = time.time()
        self.metrics.increment("total_chat_completions")
        
        try:
            headers = self._build_headers(request)
            payload = self._build_chat_payload(request)
            
            self.logger.info(
                f"[{request_id}] Making OpenRouter chat completion request with model: {request.model}"
            )
            
            response = requests.post(
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            response_data = response.json()
            
            completion_response = ChatCompletionResponse(
                success=True,
                request_id=request_id,
                response=response_data,
                model=request.model,
                usage=response_data.get("usage")
            )
            
            completion_time = time.time() - start_time
            self.logger.info(
                f"[{request_id}] Chat completion completed successfully in {completion_time:.3f}s"
            )
            self.metrics.increment("successful_chat_completions")
            
            return completion_response, True
            
        except requests.exceptions.RequestException as e:
            completion_time = time.time() - start_time
            self.logger.error(
                f"[{request_id}] OpenRouter API request failed: {e} - Time: {completion_time:.3f}s"
            )
            self.metrics.increment("failed_chat_completions")
            return None, False
            
        except Exception as e:
            completion_time = time.time() - start_time
            self.logger.error(
                f"[{request_id}] Unexpected error during chat completion: {e} - Time: {completion_time:.3f}s"
            )
            self.metrics.increment("failed_chat_completions")
            return None, False
    
    def list_models(self, request_id: str) -> Tuple[ModelsResponse, bool]:
        """Fetch available models from OpenRouter.
        
        Args:
            request_id: Request ID for logging
            
        Returns:
            Tuple of (models response, success status)
        """
        start_time = time.time()
        self.metrics.increment("total_model_requests")
        
        try:
            self.logger.info(f"[{request_id}] Fetching available OpenRouter models")
            
            response = requests.get(
                url=f"{self.base_url}/models",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            models_data = response.json()
            model_count = len(models_data.get('data', []))
            
            models_response = ModelsResponse(
                success=True,
                request_id=request_id,
                models=models_data,
                count=model_count
            )
            
            fetch_time = time.time() - start_time
            self.logger.info(
                f"[{request_id}] Successfully fetched {model_count} models in {fetch_time:.3f}s"
            )
            self.metrics.increment("successful_model_requests")
            
            return models_response, True
            
        except requests.exceptions.RequestException as e:
            fetch_time = time.time() - start_time
            self.logger.error(
                f"[{request_id}] Failed to fetch models: {e} - Time: {fetch_time:.3f}s"
            )
            self.metrics.increment("failed_model_requests")
            return None, False
            
        except Exception as e:
            fetch_time = time.time() - start_time
            self.logger.error(
                f"[{request_id}] Unexpected error fetching models: {e} - Time: {fetch_time:.3f}s"
            )
            self.metrics.increment("failed_model_requests")
            return None, False
    
    def _build_headers(self, request: ChatCompletionRequest) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Authorization": f"Bearer {request.api_key}",
            "Content-Type": "application/json",
        }
        
        if request.site_url:
            headers["HTTP-Referer"] = request.site_url
        if request.site_name:
            headers["X-Title"] = request.site_name
            
        return headers
    
    def _build_chat_payload(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Build chat completion payload."""
        payload = {
            "model": request.model,
            "messages": request.messages,
        }
        
        # Add optional parameters if provided
        optional_fields = [
            "max_tokens", "temperature", "top_p", 
            "frequency_penalty", "presence_penalty", "stream"
        ]
        
        for field in optional_fields:
            value = getattr(request, field)
            if value is not None:
                payload[field] = value
                
        return payload