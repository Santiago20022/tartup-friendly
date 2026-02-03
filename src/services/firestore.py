from datetime import datetime
from typing import Optional
from google.cloud import firestore
import structlog

from src.config import get_settings
from src.models.schemas import Document, DocumentStatus

logger = structlog.get_logger(__name__)


class FirestoreService:
    """
    Firestore service for document metadata storage.
    Handles CRUD operations for ultrasound report records.
    """

    COLLECTION_DOCUMENTS = "documents"

    def __init__(self):
        self.settings = get_settings()
        self.client = firestore.Client(project=self.settings.gcp_project_id)

    def _doc_ref(self, document_id: str):
        """Get document reference."""
        return self.client.collection(self.COLLECTION_DOCUMENTS).document(document_id)

    async def create_document(self, document: Document) -> Document:
        """Create a new document record."""
        doc_ref = self._doc_ref(document.id)
        doc_data = document.model_dump(mode="json")

        # Convert datetime to Firestore timestamp
        doc_data["created_at"] = document.created_at
        doc_data["updated_at"] = document.updated_at

        doc_ref.set(doc_data)

        logger.info(
            "document_created",
            document_id=document.id,
            owner_id=document.owner_id
        )

        return document

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        doc_ref = self._doc_ref(document_id)
        doc_snapshot = doc_ref.get()

        if not doc_snapshot.exists:
            return None

        data = doc_snapshot.to_dict()
        return Document(**data)

    async def update_document(
        self,
        document_id: str,
        updates: dict
    ) -> Optional[Document]:
        """Update document fields."""
        doc_ref = self._doc_ref(document_id)

        # Add updated timestamp
        updates["updated_at"] = datetime.utcnow()

        doc_ref.update(updates)

        logger.info(
            "document_updated",
            document_id=document_id,
            fields=list(updates.keys())
        )

        return await self.get_document(document_id)

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        """Update document processing status."""
        updates = {"status": status.value}

        if error_message:
            updates["error_message"] = error_message

        if status == DocumentStatus.COMPLETED:
            updates["processed_at"] = datetime.utcnow()

        return await self.update_document(document_id, updates)

    async def list_documents(
        self,
        owner_id: str,
        status: Optional[DocumentStatus] = None,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> tuple[list[Document], Optional[str]]:
        """
        List documents for a user with pagination.
        Returns (documents, next_cursor).
        """
        query = (
            self.client.collection(self.COLLECTION_DOCUMENTS)
            .where("owner_id", "==", owner_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )

        if status:
            query = query.where("status", "==", status.value)

        if cursor:
            # Start after the cursor document
            cursor_doc = self._doc_ref(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)

        # Fetch one extra to determine if there are more results
        docs = query.limit(limit + 1).stream()
        documents = []
        next_cursor = None

        for i, doc in enumerate(docs):
            if i < limit:
                documents.append(Document(**doc.to_dict()))
            else:
                # There are more results
                next_cursor = documents[-1].id if documents else None

        return documents, next_cursor

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document record."""
        doc_ref = self._doc_ref(document_id)

        if not doc_ref.get().exists:
            return False

        doc_ref.delete()

        logger.info("document_deleted", document_id=document_id)
        return True


# Singleton instance
_firestore_service: Optional[FirestoreService] = None


def get_firestore_service() -> FirestoreService:
    """Get or create Firestore service instance."""
    global _firestore_service
    if _firestore_service is None:
        _firestore_service = FirestoreService()
    return _firestore_service
