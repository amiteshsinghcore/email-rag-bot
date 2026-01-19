"""
Vector Store Service

Manages ChromaDB for storing and retrieving email embeddings.
"""

import hashlib
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.config import settings


class VectorStoreService:
    """
    Service for managing vector embeddings in ChromaDB.

    Handles storage, retrieval, and similarity search for email content.
    """

    # Collection names
    EMAIL_COLLECTION = "email_chunks"
    ATTACHMENT_COLLECTION = "attachment_chunks"

    def __init__(self) -> None:
        """Initialize ChromaDB client."""
        self._client: chromadb.ClientAPI | None = None
        self._email_collection: chromadb.Collection | None = None
        self._attachment_collection: chromadb.Collection | None = None

    @property
    def client(self) -> chromadb.ClientAPI:
        """Get or create ChromaDB client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> chromadb.ClientAPI:
        """Create ChromaDB client based on configuration."""
        if settings.app_env == "test":
            # Use ephemeral client for testing
            logger.info("Using ephemeral ChromaDB client for testing")
            return chromadb.Client()

        if settings.chroma_host and settings.chroma_port:
            # Use HTTP client for remote ChromaDB
            logger.info(
                f"Connecting to ChromaDB at {settings.chroma_host}:{settings.chroma_port}"
            )
            return chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )

        # Use persistent client for local development
        logger.info(f"Using persistent ChromaDB at {settings.chroma_persist_directory}")
        return chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

    @property
    def email_collection(self) -> chromadb.Collection:
        """Get or create email embeddings collection."""
        if self._email_collection is None:
            self._email_collection = self.client.get_or_create_collection(
                name=self.EMAIL_COLLECTION,
                metadata={
                    "hnsw:space": "cosine",  # Use cosine similarity
                    "hnsw:construction_ef": 200,  # Higher for better recall
                    "hnsw:search_ef": 100,
                    "description": "Email content embeddings for semantic search",
                },
            )
            logger.info(
                f"Email collection initialized with {self._email_collection.count()} documents"
            )
        return self._email_collection

    @property
    def attachment_collection(self) -> chromadb.Collection:
        """Get or create attachment embeddings collection."""
        if self._attachment_collection is None:
            self._attachment_collection = self.client.get_or_create_collection(
                name=self.ATTACHMENT_COLLECTION,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 100,
                    "description": "Attachment content embeddings for semantic search",
                },
            )
            logger.info(
                f"Attachment collection initialized with "
                f"{self._attachment_collection.count()} documents"
            )
        return self._attachment_collection

    def add_email_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """
        Add email embeddings to the collection.

        Args:
            ids: Unique identifiers for each embedding
            embeddings: Vector embeddings (384 dimensions for all-MiniLM-L6-v2)
            documents: Original text content
            metadatas: Metadata for filtering (email_id, pst_file_id, sender, date, etc.)
        """
        if not ids:
            return

        self.email_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug(f"Added {len(ids)} email embeddings to collection")

    def add_attachment_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add attachment embeddings to the collection."""
        if not ids:
            return

        self.attachment_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug(f"Added {len(ids)} attachment embeddings to collection")

    def search_emails(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Search for similar emails using vector similarity.

        Args:
            query_embedding: Query vector (384 dimensions)
            n_results: Number of results to return
            where: Metadata filter (e.g., {"pst_file_id": "..."})
            where_document: Document content filter

        Returns:
            Dictionary with ids, distances, documents, and metadatas
        """
        results = self.email_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )

        # Flatten results (query returns nested lists)
        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
        }

    def search_attachments(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search for similar attachments using vector similarity."""
        results = self.attachment_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
        }

    def delete_by_pst_file(self, pst_file_id: str) -> None:
        """Delete all embeddings associated with a PST file."""
        # Delete from email collection
        self.email_collection.delete(where={"pst_file_id": pst_file_id})
        logger.info(f"Deleted email embeddings for PST file {pst_file_id}")

        # Delete from attachment collection
        self.attachment_collection.delete(where={"pst_file_id": pst_file_id})
        logger.info(f"Deleted attachment embeddings for PST file {pst_file_id}")

    def delete_by_email_id(self, email_id: str) -> None:
        """Delete embeddings for a specific email."""
        self.email_collection.delete(where={"email_id": email_id})

    def get_collection_stats(self) -> dict[str, int]:
        """Get statistics about the collections."""
        return {
            "email_count": self.email_collection.count(),
            "attachment_count": self.attachment_collection.count(),
        }

    def reset_collections(self) -> None:
        """Reset all collections (use with caution!)."""
        self.client.delete_collection(self.EMAIL_COLLECTION)
        self.client.delete_collection(self.ATTACHMENT_COLLECTION)
        self._email_collection = None
        self._attachment_collection = None
        logger.warning("All vector collections have been reset")

    @staticmethod
    def generate_chunk_id(email_id: str, chunk_index: int) -> str:
        """Generate a unique ID for an email chunk."""
        return f"{email_id}_chunk_{chunk_index}"

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate a hash for content deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Global instance
vector_store = VectorStoreService()


def get_vector_store() -> VectorStoreService:
    """Get the vector store service instance."""
    return vector_store
