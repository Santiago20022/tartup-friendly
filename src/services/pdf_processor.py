import io
import uuid
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image
import structlog

from src.models.schemas import ImageMetadata

logger = structlog.get_logger(__name__)


class PDFProcessor:
    """
    PDF processing utilities for image extraction.
    Uses PyMuPDF (fitz) for efficient PDF manipulation.
    """

    def __init__(self, min_image_size: int = 100, max_image_size_mb: float = 2.0):
        self.min_image_size = min_image_size  # Minimum width/height in pixels
        self.max_image_size_bytes = int(max_image_size_mb * 1024 * 1024)

    async def extract_images(self, pdf_content: bytes) -> list[tuple[bytes, ImageMetadata]]:
        """
        Extract all images from a PDF document.
        Returns list of (image_bytes, metadata) tuples.
        """
        images = []

        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)

                        if base_image:
                            image_bytes = base_image["image"]
                            img_ext = base_image["ext"]
                            width = base_image.get("width", 0)
                            height = base_image.get("height", 0)

                            # Skip small images (likely icons or artifacts)
                            if width < self.min_image_size or height < self.min_image_size:
                                continue

                            # Compress if too large
                            if len(image_bytes) > self.max_image_size_bytes:
                                image_bytes, img_ext = self._compress_image(image_bytes)

                            image_id = str(uuid.uuid4())
                            metadata = ImageMetadata(
                                id=image_id,
                                gcs_path="",  # Will be set after upload
                                page_number=page_num + 1,
                                width=width,
                                height=height,
                                format=img_ext,
                                size_bytes=len(image_bytes)
                            )

                            images.append((image_bytes, metadata))

                            logger.debug(
                                "image_extracted",
                                page=page_num + 1,
                                width=width,
                                height=height,
                                size_bytes=len(image_bytes)
                            )

                    except Exception as e:
                        logger.warning(
                            "image_extraction_failed",
                            page=page_num + 1,
                            error=str(e)
                        )
                        continue

            doc.close()

        except Exception as e:
            logger.error("pdf_processing_failed", error=str(e))
            raise

        logger.info("images_extracted", count=len(images))
        return images

    def _compress_image(self, image_bytes: bytes, quality: int = 85) -> tuple[bytes, str]:
        """Compress image to reduce size while maintaining quality."""
        try:
            img = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if very large
            max_dimension = 2000
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Save as JPEG
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue(), "jpeg"

        except Exception as e:
            logger.warning("image_compression_failed", error=str(e))
            return image_bytes, "png"

    async def get_page_count(self, pdf_content: bytes) -> int:
        """Get the number of pages in a PDF."""
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    async def validate_pdf(self, pdf_content: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate that the content is a valid PDF.
        Returns (is_valid, error_message).
        """
        # Check magic bytes
        if not pdf_content.startswith(b"%PDF"):
            return False, "Invalid PDF: missing PDF header"

        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            page_count = len(doc)
            doc.close()

            if page_count == 0:
                return False, "Invalid PDF: no pages found"

            return True, None

        except Exception as e:
            return False, f"Invalid PDF: {str(e)}"


# Singleton instance
_pdf_processor: Optional[PDFProcessor] = None


def get_pdf_processor() -> PDFProcessor:
    """Get or create PDF processor instance."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor
