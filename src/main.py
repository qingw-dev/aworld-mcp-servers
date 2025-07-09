"""Main application entry point for the search server."""

import logging
import uuid

from flask import Flask, g, request

from .browser_use import browser_bp
from .config import get_settings
from .metrics import get_metrics_collector
from .openrouter import openrouter_bp
from .rag.api.health import health_bp
from .rag.api.search import search_bp
from .server_logging import get_logger, setup_logging


def create_app(name: str = None) -> Flask:
    """Application factory for creating Flask app instances.

    Returns:
        Configured Flask application
    """
    # Get settings
    settings = get_settings()

    # Setup logging
    setup_logging(settings.log_level, settings.log_file)
    logger = get_logger(__name__)

    # Create Flask app
    app = Flask(name or __name__)
    app.config["DEBUG"] = settings.debug

    # Initialize metrics collector
    metrics_collector = get_metrics_collector()

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(openrouter_bp)
    app.register_blueprint(browser_bp)

    # Add request ID to all requests
    @app.before_request
    def add_request_id():
        """Add unique request ID to each request."""
        g.request_id = str(uuid.uuid4())[:8]

    # Log all requests
    @app.after_request
    def log_request(response):
        """Log request details after processing."""
        logger.info(
            f"[{getattr(g, 'request_id', 'unknown')}] {request.method} {request.path} - "
            f"Status: {response.status_code} - IP: {request.remote_addr}"
        )
        return response

    logger.info(f"Search server initialized - Debug: {settings.debug}")
    return app


def main() -> None:
    """Main entry point for running the server."""
    settings = get_settings()
    app: Flask = create_app()

    logger: logging.Logger = get_logger(__name__)
    logger.info(f"Starting search server on {settings.host}:{settings.port}")

    app.run(host=settings.host, port=settings.port, debug=settings.debug, threaded=True)


if __name__ == "__main__":
    main()
