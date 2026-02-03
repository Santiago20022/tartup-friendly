import pytest


def test_unauthenticated_request_rejected(test_client):
    """Test that requests without auth are rejected."""
    response = test_client.get("/api/v1/documents")
    assert response.status_code == 401


def test_invalid_api_key_rejected(test_client):
    """Test that invalid API keys are rejected."""
    response = test_client.get(
        "/api/v1/documents",
        headers={"X-API-Key": "invalid-key-12345"}
    )
    assert response.status_code == 401


def test_valid_api_key_accepted(test_client, auth_headers):
    """Test that valid API keys are accepted."""
    response = test_client.get("/api/v1/documents", headers=auth_headers)
    # Should return 200 (empty list) not 401
    assert response.status_code == 200


def test_bearer_token_format(test_client):
    """Test Bearer token authentication."""
    response = test_client.get(
        "/api/v1/documents",
        headers={"Authorization": "Bearer demo-token-testuser"}
    )
    assert response.status_code == 200
