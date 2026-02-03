import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application."""
    # Set test environment variables before importing app
    import os
    os.environ.setdefault("GCP_PROJECT_ID", "test-project")
    os.environ.setdefault("DOCUMENTAI_PROCESSOR_ID", "test-processor")

    from src.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers():
    """Return headers with demo API key for authenticated requests."""
    return {"X-API-Key": "demo-api-key-12345"}


@pytest.fixture
def sample_pdf_content():
    """Return minimal valid PDF content for testing."""
    # Minimal PDF structure
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer << /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
