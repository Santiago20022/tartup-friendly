import pytest
from io import BytesIO


def test_upload_requires_pdf(test_client, auth_headers):
    """Test that only PDF files are accepted."""
    # Try uploading a text file
    response = test_client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.txt", b"not a pdf", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_validates_extension(test_client, auth_headers):
    """Test that file extension is validated."""
    response = test_client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("test.doc", b"content", "application/msword")}
    )
    assert response.status_code == 400


def test_list_documents_empty(test_client, auth_headers):
    """Test listing documents returns empty list for new user."""
    response = test_client.get("/api/v1/documents", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)


def test_get_nonexistent_document(test_client, auth_headers):
    """Test getting a document that doesn't exist."""
    response = test_client.get(
        "/api/v1/documents/nonexistent-id",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_nonexistent_document(test_client, auth_headers):
    """Test deleting a document that doesn't exist."""
    response = test_client.delete(
        "/api/v1/documents/nonexistent-id",
        headers=auth_headers
    )
    assert response.status_code == 404
