def test_health_endpoint(test_client):
    """Test health check endpoint returns 200."""
    response = test_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_root_endpoint(test_client):
    """Test root endpoint returns API info."""
    response = test_client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "VetUltrasound API"
    assert "version" in data
