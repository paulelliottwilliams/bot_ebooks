"""IndividualEvaluation model - stores each provider+persona evaluation."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .ebook import Ebook
    from .evaluation import Evaluation


class IndividualEvaluation(Base):
    """
    A single evaluation from one provider+persona combination.

    The main Evaluation record aggregates these individual evaluations.
    Storing them separately allows:
    - Transparency into how different evaluators scored
    - Training data for future custom models
    - Analysis of evaluator agreement/disagreement
    """

    __tablename__ = "individual_evaluations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Reference to parent evaluation
    evaluation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, index=True
    )

    # Reference to ebook (denormalized for easier querying)
    ebook_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ebooks.id"), nullable=False, index=True
    )

    # Provider and persona identification
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # claude, openai, gemini
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # specific model version
    persona_id: Mapped[str] = mapped_column(String(50), nullable=False)  # rigorist, synthesizer, etc.

    # The Four Dimensions (1-10 scale) - raw scores from this evaluator
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

    # Weighted score using this persona's weights
    weighted_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True
    )

    # Detailed feedback from this evaluator
    novelty_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structure_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thoroughness_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clarity_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overall_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Raw LLM response for debugging/training
    raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Error tracking
    success: Mapped[bool] = mapped_column(default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)  # How long the API call took

    # Relationships
    evaluation: Mapped["Evaluation"] = relationship(
        "Evaluation", back_populates="individual_evaluations"
    )
    ebook: Mapped["Ebook"] = relationship("Ebook")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_indiv_eval_provider_persona", "provider", "persona_id"),
        Index("ix_indiv_eval_ebook_provider", "ebook_id", "provider"),
    )

    def __repr__(self) -> str:
        return f"<IndividualEvaluation {self.provider}/{self.persona_id} for {self.ebook_id}>"

    @property
    def scores_dict(self) -> dict:
        """Return scores as a dictionary."""
        return {
            "novelty": float(self.novelty_score) if self.novelty_score else None,
            "structure": float(self.structure_score) if self.structure_score else None,
            "thoroughness": float(self.thoroughness_score) if self.thoroughness_score else None,
            "clarity": float(self.clarity_score) if self.clarity_score else None,
            "weighted": float(self.weighted_score) if self.weighted_score else None,
        }
