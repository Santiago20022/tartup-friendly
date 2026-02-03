import hashlib
from datetime import timedelta
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound
import structlog

from src.config import get_settings

logger = structlog.get_logger(__name__)


class StorageService:
    """
    Google Cloud Storage service for managing PDFs and images.
    Handles uploads, downloads, and signed URL generation.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = storage.Client(project=self.settings.gcp_project_id)
        self.uploads_bucket = self.client.bucket(self.settings.gcs_bucket_uploads)
        self.images_bucket = self.client.bucket(self.settings.gcs_bucket_images)

    def _calculate_checksum(self, content: bytes) -> str:
        """Calculate SHA-256 checksum of file content."""
        return hashlib.sha256(content).hexdigest()

    async def upload_pdf(
        self,
        content: bytes,
        user_id: str,
        document_id: str,
        filename: str
    ) -> tuple[str, str]:
        """
        Upload PDF to Cloud Storage.
        Returns (gcs_path, checksum).
        """
        # Sanitize filename and build path
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        gcs_path = f"{user_id}/{document_id}/{safe_filename}"

        blob = self.uploads_bucket.blob(gcs_path)

        # Set content type and metadata
        blob.content_type = "application/pdf"
        blob.metadata = {
            "user_id": user_id,
            "document_id": document_id,
            "original_filename": filename
        }

        # Upload with checksum validation
        checksum = self._calculate_checksum(content)
        blob.upload_from_string(content, content_type="application/pdf")

        logger.info(
            "pdf_uploaded",
            gcs_path=gcs_path,
            size_bytes=len(content),
            checksum=checksum[:16]
        )

        return gcs_path, checksum

    async def upload_image(
        self,
        content: bytes,
        user_id: str,
        document_id: str,
        image_id: str,
        content_type: str = "image/png"
    ) -> str:
        """
        Upload extracted image to Cloud Storage.
        Returns gcs_path.
        """
        extension = "png" if "png" in content_type else "jpg"
        gcs_path = f"{user_id}/{document_id}/{image_id}.{extension}"

        blob = self.images_bucket.blob(gcs_path)
        blob.content_type = content_type
        blob.metadata = {
            "document_id": document_id,
            "image_id": image_id
        }

        blob.upload_from_string(content, content_type=content_type)

        logger.info(
            "image_uploaded",
            gcs_path=gcs_path,
            size_bytes=len(content)
        )

        return gcs_path

    async def download_pdf(self, gcs_path: str) -> Optional[bytes]:
        """Download PDF from Cloud Storage."""
        try:
            blob = self.uploads_bucket.blob(gcs_path)
            return blob.download_as_bytes()
        except NotFound:
            logger.warning("pdf_not_found", gcs_path=gcs_path)
            return None

    async def generate_signed_url(
        self,
        gcs_path: str,
        bucket_type: str = "images",
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for secure, time-limited access.
        """
        bucket = self.images_bucket if bucket_type == "images" else self.uploads_bucket
        blob = bucket.blob(gcs_path)

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )

        return url

    async def delete_document_files(self, user_id: str, document_id: str) -> None:
        """Delete all files associated with a document."""
        prefix = f"{user_id}/{document_id}/"

        # Delete from uploads bucket
        blobs = self.uploads_bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            blob.delete()
            logger.info("file_deleted", bucket="uploads", path=blob.name)

        # Delete from images bucket
        blobs = self.images_bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            blob.delete()
            logger.info("file_deleted", bucket="images", path=blob.name)


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
