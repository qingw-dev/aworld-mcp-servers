"""FastAPI application entry point for the search server."""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .browser_use.api.browser_fastapi import browser_router
from .config import get_settings
from .openrouter.api.llm_fastapi import openrouter_router
from .rag.api.health_fastapi import health_router
from .rag.api.search_fastapi import search_router
from .server_logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_file)
    logger = get_logger(__name__)
    logger.info(f"FastAPI search server initialized - Debug: {settings.debug}")

    yield

    # Shutdown
    logger.info("FastAPI search server shutting down")


def create_app() -> FastAPI:
    """Application factory for creating FastAPI app instances.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Search Server API",
        description="High-performance search and RAG API",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(openrouter_router)
    app.include_router(browser_router)

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add unique request ID to each request."""
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        logger = get_logger(__name__)
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Time: {process_time:.3f}s - "
            f"IP: {request.client.host}"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        return response

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.main_fastapi:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else 4,
        log_level=settings.log_level.lower(),
    )
