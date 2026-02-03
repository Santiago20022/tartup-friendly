from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


class DocumentStatus(str, Enum):
    """Processing status for uploaded documents."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PatientInfo(BaseModel):
    """Extracted patient information from the ultrasound report."""
    name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    age: Optional[str] = None
    weight: Optional[str] = None
    sex: Optional[str] = None
    microchip_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OwnerInfo(BaseModel):
    """Pet owner contact information."""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class VeterinarianInfo(BaseModel):
    """Veterinarian details from the report."""
    name: Optional[str] = None
    license_number: Optional[str] = None
    clinic_name: Optional[str] = None
    specialization: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class DiagnosisInfo(BaseModel):
    """Diagnostic findings from the ultrasound."""
    primary: Optional[str] = None
    secondary: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    severity: Optional[str] = None
    raw_text: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class Recommendation(BaseModel):
    """Treatment or follow-up recommendations."""
    type: Optional[str] = None  # medication, procedure, followup, other
    description: str
    priority: Optional[str] = None  # low, medium, high

    model_config = ConfigDict(extra="allow")


class ImageMetadata(BaseModel):
    """Metadata for extracted ultrasound images."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gcs_path: str
    page_number: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None
    signed_url: Optional[str] = None  # Populated on GET requests

    model_config = ConfigDict(extra="allow")


class ExtractedData(BaseModel):
    """Complete extracted data from the PDF report."""
    patient: PatientInfo = Field(default_factory=PatientInfo)
    owner: OwnerInfo = Field(default_factory=OwnerInfo)
    veterinarian: VeterinarianInfo = Field(default_factory=VeterinarianInfo)
    diagnosis: DiagnosisInfo = Field(default_factory=DiagnosisInfo)
    recommendations: list[Recommendation] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class OriginalFile(BaseModel):
    """Original uploaded file metadata."""
    gcs_path: str
    filename: str
    size_bytes: int
    mime_type: str
    checksum_sha256: Optional[str] = None


class Document(BaseModel):
    """Complete document record stored in Firestore."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str
    status: DocumentStatus = DocumentStatus.UPLOADING
    error_message: Optional[str] = None

    original_file: Optional[OriginalFile] = None
    extracted_data: Optional[ExtractedData] = None
    images: list[ImageMetadata] = Field(default_factory=list)

    # Processing metadata
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="allow")


# API Response Models

class DocumentUploadResponse(BaseModel):
    """Response returned after successful upload."""
    document_id: str
    status: DocumentStatus
    message: str


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: list[Document]
    total_count: int
    next_cursor: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str
    detail: Optional[str] = None
    code: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
