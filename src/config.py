from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GCP Configuration
    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="us-central1", alias="GCP_REGION")

    # Cloud Storage
    gcs_bucket_uploads: str = Field(default="vet-ultrasound-uploads", alias="GCS_BUCKET_UPLOADS")
    gcs_bucket_images: str = Field(default="vet-ultrasound-images", alias="GCS_BUCKET_IMAGES")

    # Document AI
    documentai_processor_id: str = Field(..., alias="DOCUMENTAI_PROCESSOR_ID")
    documentai_location: str = Field(default="us", alias="DOCUMENTAI_LOCATION")

    # API Settings
    api_version: str = Field(default="v1", alias="API_VERSION")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8080, alias="API_PORT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Security
    api_key_header: str = Field(default="X-API-Key", alias="API_KEY_HEADER")
    jwt_algorithm: str = Field(default="RS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")

    # File Upload Limits
    max_file_size_mb: int = Field(default=50)
    allowed_mime_types: list[str] = Field(default=["application/pdf"])

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
