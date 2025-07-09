"""Metrics collection and management."""

import threading
import time
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel, Field


class SearchMetrics(BaseModel):
    """Model for search service metrics."""

    requests: dict[str, int | float] = Field(..., description="Request metrics")
    searches: dict[str, int | float] = Field(..., description="Search metrics")
    content_fetches: dict[str, int | float] = Field(..., description="Content fetch metrics")
    performance: dict[str, float | int] = Field(..., description="Performance metrics")


class MetricsCollector:
    """Thread-safe metrics collector for the search service."""

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._lock = threading.Lock()
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_content_fetches": 0,
            "successful_content_fetches": 0,
            "failed_content_fetches": 0,
            "response_times": [],
        }

    def increment(self, metric_name: str, value: float = 1.0) -> None:
        """Increment a metric value thread-safely.

        Args:
            metric_name: Name of the metric to increment
            value: Value to add (default 1.0)
        """
        with self._lock:
            if metric_name in self._metrics:
                if metric_name == "response_times":
                    self._metrics[metric_name].append(value)
                    # Keep only last 1000 response times for memory efficiency
                    if len(self._metrics[metric_name]) > 1000:
                        self._metrics[metric_name] = self._metrics[metric_name][-1000:]
                else:
                    self._metrics[metric_name] += value

    def get_metrics(self) -> SearchMetrics:
        """Get current metrics as a SearchMetrics model.

        Returns:
            Current metrics data
        """
        with self._lock:
            metrics_copy = self._metrics.copy()

        # Calculate derived metrics
        total_requests = metrics_copy["total_requests"]
        successful_requests = metrics_copy["successful_requests"]
        failed_requests = metrics_copy["failed_requests"]

        total_searches = metrics_copy["total_searches"]
        successful_searches = metrics_copy["successful_searches"]
        failed_searches = metrics_copy["failed_searches"]

        total_content_fetches = metrics_copy["total_content_fetches"]
        successful_content_fetches = metrics_copy["successful_content_fetches"]
        failed_content_fetches = metrics_copy["failed_content_fetches"]

        response_times = metrics_copy["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        return SearchMetrics(
            requests={
                "total": total_requests,
                "successful": successful_requests,
                "failed": failed_requests,
                "success_rate": (successful_requests / max(total_requests, 1)) * 100,
            },
            searches={
                "total": total_searches,
                "successful": successful_searches,
                "failed": failed_searches,
                "success_rate": (successful_searches / max(total_searches, 1)) * 100,
            },
            content_fetches={
                "total": total_content_fetches,
                "successful": successful_content_fetches,
                "failed": failed_content_fetches,
                "success_rate": (successful_content_fetches / max(total_content_fetches, 1)) * 100,
            },
            performance={
                "average_response_time": round(avg_response_time, 3),
                "total_response_times_recorded": len(response_times),
            },
        )

    def log_performance(self, func: Callable) -> Callable:
        """Decorator to log performance metrics for functions.

        Args:
            func: Function to be decorated

        Returns:
            Wrapped function with performance logging
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            self.increment("total_requests")

            try:
                result = func(*args, **kwargs)
                self.increment("successful_requests")
                return result
            except Exception:
                self.increment("failed_requests")
                raise
            finally:
                response_time = time.time() - start_time
                self.increment("response_times", response_time)

        return wrapper


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        Global metrics collector
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
