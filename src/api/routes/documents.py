import time
import magic
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, BackgroundTasks
import structlog

from src.config import get_settings
from src.api.middleware.auth import AuthContext, get_current_user, require_scope
from src.models.schemas import (
    Document, DocumentStatus, DocumentUploadResponse,
    DocumentListResponse, OriginalFile, ErrorResponse
)
from src.services.storage import get_storage_service
from src.services.firestore import get_firestore_service
from src.services.document_ai import get_document_ai_service
from src.services.pdf_processor import get_pdf_processor

logger = structlog.get_logger(__name__)
router = APIRouter()


async def process_document_async(document_id: str, user_id: str, pdf_content: bytes):
    """
    Background task to process uploaded PDF.

    This runs after the upload endpoint returns, so the user doesn't have to wait.
    Typical processing time is 2-5 seconds depending on PDF size.
    """
    # TODO: Consider moving this to Cloud Tasks for better reliability in production
    start_time = time.time()
    firestore = get_firestore_service()
    storage = get_storage_service()
    document_ai = get_document_ai_service()
    pdf_processor = get_pdf_processor()

    try:
        logger.info("starting_document_processing", document_id=document_id)

        # Update status to processing
        await firestore.update_status(document_id, DocumentStatus.PROCESSING)

        # Extract data with Document AI
        extracted_data, confidence = await document_ai.process_document(pdf_content)

        # Extract images from PDF
        images = await pdf_processor.extract_images(pdf_content)

        # Upload extracted images to GCS
        image_metadata_list = []
        for image_bytes, metadata in images:
            content_type = f"image/{metadata.format}"
            gcs_path = await storage.upload_image(
                content=image_bytes,
                user_id=user_id,
                document_id=document_id,
                image_id=metadata.id,
                content_type=content_type
            )
            metadata.gcs_path = gcs_path
            image_metadata_list.append(metadata)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update document with extracted data
        await firestore.update_document(document_id, {
            "status": DocumentStatus.COMPLETED.value,
            "extracted_data": extracted_data.model_dump(),
            "images": [img.model_dump() for img in image_metadata_list],
            "confidence_score": confidence,
            "processing_time_ms": processing_time_ms,
            "processed_at": datetime.utcnow()
        })

        logger.info(
            "document_processing_completed",
            document_id=document_id,
            images_count=len(image_metadata_list),
            processing_time_ms=processing_time_ms
        )

    except Exception as e:
        logger.error(
            "document_processing_failed",
            document_id=document_id,
            error=str(e)
        )
        await firestore.update_status(
            document_id,
            DocumentStatus.FAILED,
            error_message=str(e)
        )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse}
    }
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload"),
    auth: AuthContext = Depends(require_scope("documents:write"))
):
    """
    Upload a veterinary ultrasound PDF report for processing.

    The document will be processed asynchronously. Use the returned document_id
    to check processing status and retrieve extracted data.

    **Authentication:** Requires valid API key or Bearer token with `documents:write` scope.
    """
    settings = get_settings()

    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    max_size = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed ({settings.max_file_size_mb}MB)"
        )

    # Validate MIME type using magic bytes
    mime_type = magic.from_buffer(content, mime=True)
    if mime_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {mime_type}. Only PDF files are accepted."
        )

    # Validate PDF structure
    pdf_processor = get_pdf_processor()
    is_valid, error_msg = await pdf_processor.validate_pdf(content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Generate document ID and upload to GCS
    import uuid
    document_id = str(uuid.uuid4())

    storage = get_storage_service()
    gcs_path, checksum = await storage.upload_pdf(
        content=content,
        user_id=auth.user_id,
        document_id=document_id,
        filename=file.filename
    )

    # Create document record in Firestore
    document = Document(
        id=document_id,
        owner_id=auth.user_id,
        status=DocumentStatus.UPLOADING,
        original_file=OriginalFile(
            gcs_path=gcs_path,
            filename=file.filename,
            size_bytes=len(content),
            mime_type=mime_type,
            checksum_sha256=checksum
        )
    )

    firestore = get_firestore_service()
    await firestore.create_document(document)

    # Schedule background processing
    background_tasks.add_task(
        process_document_async,
        document_id=document_id,
        user_id=auth.user_id,
        pdf_content=content
    )

    logger.info(
        "document_upload_accepted",
        document_id=document_id,
        filename=file.filename,
        size_bytes=len(content),
        user_id=auth.user_id
    )

    return DocumentUploadResponse(
        document_id=document_id,
        status=DocumentStatus.UPLOADING,
        message="Document uploaded successfully. Processing will begin shortly."
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    responses={401: {"model": ErrorResponse}}
)
async def list_documents(
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    auth: AuthContext = Depends(require_scope("documents:read"))
):
    """
    List all documents for the authenticated user.

    Supports pagination via cursor and filtering by processing status.

    **Authentication:** Requires valid API key or Bearer token with `documents:read` scope.
    """
    firestore = get_firestore_service()

    documents, next_cursor = await firestore.list_documents(
        owner_id=auth.user_id,
        status=status_filter,
        limit=limit,
        cursor=cursor
    )

    return DocumentListResponse(
        documents=documents,
        total_count=len(documents),
        next_cursor=next_cursor
    )


@router.get(
    "/{document_id}",
    response_model=Document,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def get_document(
    document_id: str,
    auth: AuthContext = Depends(require_scope("documents:read"))
):
    """
    Retrieve a specific document with extracted data and images.

    Images are returned with signed URLs valid for 1 hour.

    **Authentication:** Requires valid API key or Bearer token with `documents:read` scope.
    """
    firestore = get_firestore_service()
    document = await firestore.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Security: return 404 instead of 403 to avoid leaking document existence
    if document.owner_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Generate signed URLs for images
    if document.images:
        storage = get_storage_service()
        for image in document.images:
            image.signed_url = await storage.generate_signed_url(
                gcs_path=image.gcs_path,
                bucket_type="images",
                expiration_minutes=60
            )

    return document


@router.get(
    "/{document_id}/images",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def get_document_images(
    document_id: str,
    auth: AuthContext = Depends(require_scope("documents:read"))
):
    """
    Retrieve images for a specific document with signed URLs.

    **Authentication:** Requires valid API key or Bearer token with `documents:read` scope.
    """
    firestore = get_firestore_service()
    document = await firestore.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if document.owner_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if not document.images:
        return {"images": [], "document_id": document_id}

    # Generate signed URLs
    storage = get_storage_service()
    images_with_urls = []

    for image in document.images:
        image.signed_url = await storage.generate_signed_url(
            gcs_path=image.gcs_path,
            bucket_type="images",
            expiration_minutes=60
        )
        images_with_urls.append(image)

    return {
        "document_id": document_id,
        "images": images_with_urls,
        "count": len(images_with_urls)
    }


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def delete_document(
    document_id: str,
    auth: AuthContext = Depends(require_scope("documents:write"))
):
    """
    Delete a document and all associated files.

    **Authentication:** Requires valid API key or Bearer token with `documents:write` scope.
    """
    firestore = get_firestore_service()
    document = await firestore.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if document.owner_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Delete files from GCS
    storage = get_storage_service()
    await storage.delete_document_files(auth.user_id, document_id)

    # Delete from Firestore
    await firestore.delete_document(document_id)

    logger.info(
        "document_deleted",
        document_id=document_id,
        user_id=auth.user_id
    )
