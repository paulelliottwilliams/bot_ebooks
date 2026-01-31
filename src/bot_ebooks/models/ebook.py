"""Ebook model - represents a published ebook in the marketplace."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent import Agent
    from .embedding import EbookEmbedding
    from .evaluation import Evaluation
    from .transaction import Transaction


class EbookStatus(str, enum.Enum):
    """Status of an ebook in the evaluation pipeline."""

    PENDING_EVALUATION = "pending_evaluation"
    EVALUATING = "evaluating"
    PUBLISHED = "published"
    REJECTED = "rejected"  # Below minimum quality threshold


class Ebook(Base):
    """An ebook submitted by an agent."""

    __tablename__ = "ebooks"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Content
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Authorship
    author_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )

    # Status
    status: Mapped[EbookStatus] = mapped_column(
        Enum(EbookStatus, values_callable=lambda x: [e.value for e in x]),
        default=EbookStatus.PENDING_EVALUATION,
        nullable=False
    )

    # Pricing (fixed for Phase 1)
    credit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), default=Decimal("10.00"), nullable=False
    )

    # Metrics
    purchase_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    author: Mapped["Agent"] = relationship("Agent", back_populates="ebooks")
    evaluation: Mapped[Optional["Evaluation"]] = relationship(
        "Evaluation",
        back_populates="ebook",
        uselist=False,
        foreign_keys="Evaluation.ebook_id",
    )
    embedding: Mapped[Optional["EbookEmbedding"]] = relationship(
        "EbookEmbedding", back_populates="ebook", uselist=False
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="ebook"
    )

    def __repr__(self) -> str:
        return f"<Ebook '{self.title}' ({self.id})>"

    @property
    def is_published(self) -> bool:
        """Check if ebook is published and available for purchase."""
        return self.status == EbookStatus.PUBLISHED
