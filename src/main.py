import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import documents, health
from src.api.middleware.rate_limiter import RateLimitMiddleware
from src.config import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    settings = get_settings()
    logger.info(
        "starting_application",
        project_id=settings.gcp_project_id,
        region=settings.gcp_region
    )
    yield
    logger.info("shutting_down_application")


def create_app() -> FastAPI:
    """Application factory pattern."""
    settings = get_settings()

    app = FastAPI(
        title="VetUltrasound API",
        description="API for processing veterinary ultrasound PDF reports",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )

    # Register routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(
        documents.router,
        prefix=f"/api/{settings.api_version}/documents",
        tags=["Documents"]
    )

    return app


app = create_app()
