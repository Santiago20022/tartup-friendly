from datetime import datetime
from fastapi import APIRouter

from src.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for load balancers and monitoring.
    Returns the current status and version of the API.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


@router.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "VetUltrasound API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
