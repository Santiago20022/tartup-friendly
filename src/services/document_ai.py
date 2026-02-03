import re
from typing import Optional
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
import structlog

from src.config import get_settings
from src.models.schemas import (
    ExtractedData, PatientInfo, OwnerInfo,
    VeterinarianInfo, DiagnosisInfo, Recommendation
)

logger = structlog.get_logger(__name__)


class DocumentAIService:
    """
    Google Cloud Document AI service for extracting structured data from PDFs.
    Uses the Form Parser processor to extract key-value pairs and tables.
    """

    def __init__(self):
        self.settings = get_settings()

        # Configure client for the processor location
        opts = ClientOptions(
            api_endpoint=f"{self.settings.documentai_location}-documentai.googleapis.com"
        )
        self.client = documentai.DocumentProcessorServiceClient(client_options=opts)

        # Build processor name
        self.processor_name = self.client.processor_path(
            self.settings.gcp_project_id,
            self.settings.documentai_location,
            self.settings.documentai_processor_id
        )

    async def process_document(self, content: bytes, mime_type: str = "application/pdf") -> tuple[ExtractedData, float]:
        """
        Process PDF with Document AI and extract structured data.
        Returns (extracted_data, confidence_score).
        """
        # Create the document object
        raw_document = documentai.RawDocument(
            content=content,
            mime_type=mime_type
        )

        request = documentai.ProcessRequest(
            name=self.processor_name,
            raw_document=raw_document
        )

        logger.info("processing_document_with_ai", processor=self.processor_name)

        # Process the document
        result = self.client.process_document(request=request)
        document = result.document

        # Extract text and entities
        full_text = document.text
        confidence = self._calculate_confidence(document)

        # Parse the extracted text into structured data
        extracted_data = self._parse_extracted_text(full_text, document)

        logger.info(
            "document_processed",
            text_length=len(full_text),
            confidence=confidence
        )

        return extracted_data, confidence

    def _calculate_confidence(self, document) -> float:
        """Calculate average confidence score from document."""
        confidences = []

        for page in document.pages:
            for block in page.blocks:
                if hasattr(block, 'layout') and hasattr(block.layout, 'confidence'):
                    confidences.append(block.layout.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _parse_extracted_text(self, text: str, document) -> ExtractedData:
        """
        Parse the extracted text into structured fields.
        Uses pattern matching and entity extraction.
        """
        text_lower = text.lower()

        # Extract patient information
        patient = self._extract_patient_info(text)

        # Extract owner information
        owner = self._extract_owner_info(text)

        # Extract veterinarian information
        veterinarian = self._extract_veterinarian_info(text)

        # Extract diagnosis
        diagnosis = self._extract_diagnosis_info(text)

        # Extract recommendations
        recommendations = self._extract_recommendations(text)

        return ExtractedData(
            patient=patient,
            owner=owner,
            veterinarian=veterinarian,
            diagnosis=diagnosis,
            recommendations=recommendations
        )

    def _extract_patient_info(self, text: str) -> PatientInfo:
        """Extract patient (animal) information."""
        patient = PatientInfo()

        # Common patterns for veterinary reports
        patterns = {
            "name": [
                r"(?:paciente|patient|nombre|name)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;|\s{2,})",
                r"(?:mascota|pet)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;)"
            ],
            "species": [
                r"(?:especie|species)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;)",
                r"\b(canino|felino|canine|feline|perro|gato|dog|cat)\b"
            ],
            "breed": [
                r"(?:raza|breed)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;)"
            ],
            "age": [
                r"(?:edad|age)[\s:]+(\d+[\s]*(?:años?|years?|meses?|months?|a|m))",
            ],
            "weight": [
                r"(?:peso|weight)[\s:]+(\d+[\.,]?\d*[\s]*(?:kg|lb|kilos?|pounds?))",
            ],
            "sex": [
                r"(?:sexo|sex|género|gender)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;)",
                r"\b(macho|hembra|male|female|castrado|castrated|neutro|neutered)\b"
            ]
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    setattr(patient, field, match.group(1).strip())
                    break

        return patient

    def _extract_owner_info(self, text: str) -> OwnerInfo:
        """Extract pet owner information."""
        owner = OwnerInfo()

        patterns = {
            "name": [
                r"(?:propietario|owner|dueño|tutor)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;|\s{2,})",
                r"(?:cliente|client)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\n|,|;)"
            ],
            "phone": [
                r"(?:tel[eé]fono|phone|cel|móvil|mobile)[\s:]+([+\d\s\-\(\)]+)",
            ],
            "email": [
                r"(?:email|correo|e-mail)[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
                r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
            ],
            "address": [
                r"(?:direcci[oó]n|address|domicilio)[\s:]+([A-Za-z0-9áéíóúñÁÉÍÓÚÑ\s,#\.-]+?)(?:\n|;)"
            ]
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    setattr(owner, field, match.group(1).strip())
                    break

        return owner

    def _extract_veterinarian_info(self, text: str) -> VeterinarianInfo:
        """Extract veterinarian information."""
        vet = VeterinarianInfo()

        patterns = {
            "name": [
                r"(?:veterinario|veterinarian|m[eé]dico|doctor|dr\.?)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s\.]+?)(?:\n|,|;|\s{2,})",
                r"(?:atendido por|examined by|revisado por)[\s:]+([A-Za-záéíóúñÁÉÍÓÚÑ\s\.]+?)(?:\n|,|;)"
            ],
            "license_number": [
                r"(?:c[eé]dula|license|matr[ií]cula|registro)[\s:#]+([A-Z0-9\-]+)",
            ],
            "clinic_name": [
                r"(?:cl[ií]nica|clinic|hospital|centro)[\s:]+([A-Za-z0-9áéíóúñÁÉÍÓÚÑ\s\.&]+?)(?:\n|,|;)"
            ]
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    setattr(vet, field, match.group(1).strip())
                    break

        return vet

    def _extract_diagnosis_info(self, text: str) -> DiagnosisInfo:
        """Extract diagnostic information."""
        diagnosis = DiagnosisInfo()

        # Extract the diagnosis section
        diagnosis_patterns = [
            r"(?:diagn[oó]stico|diagnosis|hallazgos|findings|conclusi[oó]n|conclusion)[\s:]+(.+?)(?=(?:recomendaci|recommendation|tratamiento|treatment|medicaci|medication|\Z))",
        ]

        for pattern in diagnosis_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                diagnosis_text = match.group(1).strip()
                diagnosis.raw_text = diagnosis_text

                # Extract individual findings (bullet points or numbered items)
                findings = re.findall(r"[-•●]\s*(.+?)(?:\n|$)", diagnosis_text)
                if not findings:
                    findings = re.findall(r"\d+[\.)\-]\s*(.+?)(?:\n|$)", diagnosis_text)

                diagnosis.findings = [f.strip() for f in findings if f.strip()]

                # First sentence as primary diagnosis
                sentences = diagnosis_text.split(".")
                if sentences:
                    diagnosis.primary = sentences[0].strip()

                break

        return diagnosis

    def _extract_recommendations(self, text: str) -> list[Recommendation]:
        """Extract treatment recommendations."""
        recommendations = []

        # Find recommendations section
        rec_patterns = [
            r"(?:recomendaci[oó]n|recommendation|tratamiento|treatment|indicaci[oó]n|plan)[\s:]+(.+?)(?=(?:firma|signature|fecha|date|observaci|nota|\Z))",
        ]

        rec_text = ""
        for pattern in rec_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                rec_text = match.group(1).strip()
                break

        if rec_text:
            # Extract individual recommendations
            items = re.findall(r"[-•●]\s*(.+?)(?:\n|$)", rec_text)
            if not items:
                items = re.findall(r"\d+[\.)\-]\s*(.+?)(?:\n|$)", rec_text)
            if not items:
                # Split by newlines
                items = [line.strip() for line in rec_text.split("\n") if line.strip()]

            for item in items:
                rec_type = self._classify_recommendation(item)
                recommendations.append(Recommendation(
                    type=rec_type,
                    description=item.strip(),
                    priority="medium"
                ))

        return recommendations

    def _classify_recommendation(self, text: str) -> str:
        """Classify recommendation type based on content."""
        text_lower = text.lower()

        medication_keywords = ["medicamento", "medication", "mg", "ml", "tableta", "tablet", "dosis", "dose"]
        procedure_keywords = ["cirug", "surgery", "operaci", "biopsia", "biopsy", "radiograf", "ecograf"]
        followup_keywords = ["control", "seguimiento", "follow", "revisión", "cita", "appointment", "días", "semanas"]

        if any(kw in text_lower for kw in medication_keywords):
            return "medication"
        elif any(kw in text_lower for kw in procedure_keywords):
            return "procedure"
        elif any(kw in text_lower for kw in followup_keywords):
            return "followup"

        return "other"


# Singleton instance
_document_ai_service: Optional[DocumentAIService] = None


def get_document_ai_service() -> DocumentAIService:
    """Get or create Document AI service instance."""
    global _document_ai_service
    if _document_ai_service is None:
        _document_ai_service = DocumentAIService()
    return _document_ai_service
