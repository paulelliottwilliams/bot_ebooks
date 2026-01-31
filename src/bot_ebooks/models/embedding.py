"""EbookEmbedding model - vector embeddings for novelty detection."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .ebook import Ebook


# OpenAI text-embedding-3-small dimension
EMBEDDING_DIMENSION = 1536


class EbookEmbedding(Base):
    """Vector embedding for an ebook, used for novelty detection."""

    __tablename__ = "ebook_embeddings"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Reference to ebook (one-to-one)
    ebook_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ebooks.id"), unique=True, nullable=False
    )

    # Full document embedding (for overall similarity)
    full_embedding: Mapped[list] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )

    # Number of chunks used to create the embedding
    chunk_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Embedding metadata
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    ebook: Mapped["Ebook"] = relationship("Ebook", back_populates="embedding")

    def __repr__(self) -> str:
        return f"<EbookEmbedding for ebook {self.ebook_id}>"
