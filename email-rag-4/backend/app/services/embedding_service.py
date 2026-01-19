"""
Embedding Service

Generates vector embeddings for email content using sentence-transformers.
Uses all-MiniLM-L6-v2 model (384 dimensions).
"""

import hashlib
from typing import Any

from loguru import logger

from app.config import settings
from app.services.vector_store import vector_store


class TextChunk:
    """Represents a chunk of text for embedding."""

    def __init__(
        self,
        text: str,
        metadata: dict[str, Any],
        chunk_index: int = 0,
    ):
        self.text = text
        self.metadata = metadata
        self.chunk_index = chunk_index
        self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique ID for this chunk."""
        email_id = self.metadata.get("email_id", "unknown")
        return f"{email_id}_chunk_{self.chunk_index}"


class EmbeddingService:
    """
    Service for generating and storing text embeddings.

    Uses sentence-transformers with the all-MiniLM-L6-v2 model
    which produces 384-dimensional embeddings optimized for
    semantic similarity tasks.
    """

    # Model configuration
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384

    # Chunking configuration
    DEFAULT_CHUNK_SIZE = 512  # tokens
    DEFAULT_CHUNK_OVERLAP = 50  # tokens
    MAX_BATCH_SIZE = 256

    def __init__(self):
        """Initialize embedding service."""
        self._model = None
        self._tokenizer = None

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            self._load_model()
        return self._model

    def _load_model(self) -> None:
        """Load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.MODEL_NAME}")
            self._model = SentenceTransformer(self.MODEL_NAME)
            logger.info("Embedding model loaded successfully")

        except ImportError:
            logger.error("sentence-transformers not installed")
            raise RuntimeError(
                "sentence-transformers is required for embeddings. "
                "Install with: pip install sentence-transformers"
            )

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            384-dimensional embedding vector
        """
        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.EMBEDDING_DIMENSION

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of 384-dimensional embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts and track indices
        non_empty_texts = []
        non_empty_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)

        # Generate embeddings for non-empty texts
        if non_empty_texts:
            embeddings = self.model.encode(
                non_empty_texts,
                convert_to_numpy=True,
                batch_size=min(len(non_empty_texts), self.MAX_BATCH_SIZE),
                show_progress_bar=len(non_empty_texts) > 100,
            )
        else:
            embeddings = []

        # Build result with zero vectors for empty texts
        result = [[0.0] * self.EMBEDDING_DIMENSION] * len(texts)
        for i, idx in enumerate(non_empty_indices):
            result[idx] = embeddings[i].tolist()

        return result

    def chunk_text(
        self,
        text: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[str]:
        """
        Split text into overlapping chunks for embedding.

        Uses a simple word-based chunking approach that respects
        sentence boundaries where possible.

        Args:
            text: Text to chunk
            chunk_size: Maximum chunk size in characters (default from config)
            chunk_overlap: Overlap between chunks in characters

        Returns:
            List of text chunks
        """
        if not text.strip():
            return []

        chunk_size = chunk_size or settings.embedding_chunk_size
        chunk_overlap = chunk_overlap or settings.embedding_chunk_overlap

        # Split into sentences (simple approach)
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If single sentence is too long, split by words
            if sentence_length > chunk_size:
                # Flush current chunk
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Split long sentence
                words = sentence.split()
                word_chunk = []
                word_length = 0

                for word in words:
                    if word_length + len(word) + 1 > chunk_size:
                        if word_chunk:
                            chunks.append(" ".join(word_chunk))
                        word_chunk = [word]
                        word_length = len(word)
                    else:
                        word_chunk.append(word)
                        word_length += len(word) + 1

                if word_chunk:
                    chunks.append(" ".join(word_chunk))

            elif current_length + sentence_length + 1 > chunk_size:
                # Start new chunk
                if current_chunk:
                    chunks.append(" ".join(current_chunk))

                # Keep overlap from end of previous chunk
                if chunk_overlap > 0 and current_chunk:
                    overlap_text = " ".join(current_chunk)
                    overlap_start = max(0, len(overlap_text) - chunk_overlap)
                    overlap = overlap_text[overlap_start:].split()
                    current_chunk = overlap + [sentence]
                    current_length = sum(len(w) + 1 for w in current_chunk)
                else:
                    current_chunk = [sentence]
                    current_length = sentence_length

            else:
                current_chunk.append(sentence)
                current_length += sentence_length + 1

        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def prepare_email_for_embedding(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        recipients: list[str],
        metadata: dict[str, Any],
    ) -> list[TextChunk]:
        """
        Prepare email content for embedding.

        Creates chunks with appropriate metadata for storage.

        Args:
            email_id: Unique email identifier
            subject: Email subject
            body: Email body text
            sender: Sender email address
            recipients: List of recipient email addresses
            metadata: Additional metadata (pst_file_id, date, etc.)

        Returns:
            List of TextChunk objects ready for embedding
        """
        chunks = []

        # Combine subject and sender info with body for better context
        header_context = f"Subject: {subject}\nFrom: {sender}\n"
        if recipients:
            header_context += f"To: {', '.join(recipients[:5])}\n"

        # Chunk the body
        body_chunks = self.chunk_text(body)

        # If no body content, create single chunk with header
        if not body_chunks:
            body_chunks = [header_context]
        else:
            # Prepend header to first chunk
            body_chunks[0] = header_context + "\n" + body_chunks[0]

        # Create TextChunk objects
        for i, chunk_text in enumerate(body_chunks):
            chunk_metadata = {
                "email_id": email_id,
                "chunk_index": i,
                "total_chunks": len(body_chunks),
                "subject": subject[:200],  # Truncate for metadata
                "sender": sender,
                **metadata,
            }

            chunks.append(TextChunk(
                text=chunk_text,
                metadata=chunk_metadata,
                chunk_index=i,
            ))

        return chunks

    async def embed_and_store_email(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        recipients: list[str],
        metadata: dict[str, Any],
    ) -> int:
        """
        Embed email content and store in vector database.

        Args:
            email_id: Unique email identifier
            subject: Email subject
            body: Email body text
            sender: Sender email address
            recipients: List of recipient email addresses
            metadata: Additional metadata

        Returns:
            Number of chunks stored
        """
        # Prepare chunks
        chunks = self.prepare_email_for_embedding(
            email_id=email_id,
            subject=subject,
            body=body,
            sender=sender,
            recipients=recipients,
            metadata=metadata,
        )

        if not chunks:
            return 0

        # Generate embeddings
        texts = [chunk.text for chunk in chunks]
        embeddings = self.generate_embeddings(texts)

        # Store in vector database
        vector_store.add_email_embeddings(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[chunk.metadata for chunk in chunks],
        )

        return len(chunks)

    async def embed_and_store_attachment(
        self,
        attachment_id: str,
        email_id: str,
        filename: str,
        content: str,
        metadata: dict[str, Any],
    ) -> int:
        """
        Embed attachment content and store in vector database.

        Args:
            attachment_id: Unique attachment identifier
            email_id: Parent email identifier
            filename: Attachment filename
            content: Extracted text content
            metadata: Additional metadata

        Returns:
            Number of chunks stored
        """
        if not content.strip():
            return 0

        # Chunk the content
        chunks = self.chunk_text(content)

        if not chunks:
            return 0

        # Generate embeddings
        embeddings = self.generate_embeddings(chunks)

        # Prepare IDs and metadata
        ids = [f"{attachment_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "attachment_id": attachment_id,
                "email_id": email_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **metadata,
            }
            for i in range(len(chunks))
        ]

        # Store in vector database
        vector_store.add_attachment_embeddings(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        return len(chunks)

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        return self.generate_embedding(query)

    def calculate_content_hash(self, content: str) -> str:
        """Calculate hash for content deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Global instance
embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """Get the embedding service instance."""
    return embedding_service
