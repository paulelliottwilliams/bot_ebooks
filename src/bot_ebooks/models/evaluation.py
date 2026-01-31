"""Evaluation model - LLM-Judge scores for an ebook."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .ebook import Ebook
    from .individual_evaluation import IndividualEvaluation


class EvaluationStatus(str, enum.Enum):
    """Status of the evaluation process."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Evaluation(Base):
    """LLM-Judge evaluation results for an ebook."""

    __tablename__ = "evaluations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Reference to ebook (one-to-one)
    ebook_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ebooks.id"), unique=True, nullable=False
    )

    # Status
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, values_callable=lambda x: [e.value for e in x]),
        default=EvaluationStatus.PENDING,
        nullable=False
    )

    # The Four Dimensions (1-10 scale)
    novelty_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )
    structure_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )
    thoroughness_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )
    clarity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )

    # Computed aggregate score (weighted average)
    overall_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )

    # Detailed feedback from LLM-Judge
    novelty_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structure_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thoroughness_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clarity_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overall_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Novelty detection metadata
    novelty_comparison_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    most_similar_ebook_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ebooks.id"), nullable=True
    )
    max_similarity_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=5, scale=4), nullable=True  # 0.0000-1.0000
    )

    # LLM metadata (for single-evaluator mode or summary)
    judge_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    judge_prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_llm_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Multi-evaluator metadata
    evaluator_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aggregation_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # median, mean, etc.

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    ebook: Mapped["Ebook"] = relationship(
        "Ebook", back_populates="evaluation", foreign_keys=[ebook_id]
    )
    most_similar_ebook: Mapped[Optional["Ebook"]] = relationship(
        "Ebook", foreign_keys=[most_similar_ebook_id]
    )
    individual_evaluations: Mapped[list["IndividualEvaluation"]] = relationship(
        "IndividualEvaluation", back_populates="evaluation", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Evaluation for ebook {self.ebook_id} ({self.status.value})>"

    @property
    def is_completed(self) -> bool:
        """Check if evaluation has completed."""
        return self.status == EvaluationStatus.COMPLETED

    @property
    def scores_dict(self) -> dict:
        """Return scores as a dictionary."""
        return {
            "novelty": float(self.novelty_score) if self.novelty_score else None,
            "structure": float(self.structure_score) if self.structure_score else None,
            "thoroughness": float(self.thoroughness_score) if self.thoroughness_score else None,
            "clarity": float(self.clarity_score) if self.clarity_score else None,
            "overall": float(self.overall_score) if self.overall_score else None,
        }
