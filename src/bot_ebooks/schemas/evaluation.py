"""Evaluation schemas for API validation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from ..models.evaluation import EvaluationStatus


class EvaluationScores(BaseModel):
    """
    Evaluation scores for the three dimensions plus overall.

    Note: Field names are legacy. Current mapping:
    - novelty_score → Ideas (40%): Novel thesis, surprising insight, fresh framing
    - structure_score → Rigor (30%): Intellectual honesty, counterarguments, evidence
    - thoroughness_score → Craft (30%): Clear prose, logical structure
    - clarity_score → (deprecated, same as craft for compatibility)
    - overall_score → Weighted average. Must be ≥8.0 to publish.
    """

    novelty_score: Optional[Decimal]
    structure_score: Optional[Decimal]
    thoroughness_score: Optional[Decimal]
    clarity_score: Optional[Decimal]
    overall_score: Optional[Decimal]


class EvaluationFeedback(BaseModel):
    """Detailed feedback for each dimension."""

    novelty_feedback: Optional[str]
    structure_feedback: Optional[str]
    thoroughness_feedback: Optional[str]
    clarity_feedback: Optional[str]
    overall_summary: Optional[str]


class NoveltyAnalysis(BaseModel):
    """Details about novelty comparison with corpus."""

    corpus_size: Optional[int]
    most_similar_ebook_id: Optional[UUID]
    max_similarity_score: Optional[Decimal]


class EvaluationResponse(BaseModel):
    """Full evaluation details."""

    id: UUID
    ebook_id: UUID
    status: EvaluationStatus
    scores: EvaluationScores
    feedback: EvaluationFeedback
    novelty_analysis: NoveltyAnalysis
    judge_model: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_evaluation(cls, evaluation) -> "EvaluationResponse":
        """Create response from Evaluation model."""
        return cls(
            id=evaluation.id,
            ebook_id=evaluation.ebook_id,
            status=evaluation.status,
            scores=EvaluationScores(
                novelty_score=evaluation.novelty_score,
                structure_score=evaluation.structure_score,
                thoroughness_score=evaluation.thoroughness_score,
                clarity_score=evaluation.clarity_score,
                overall_score=evaluation.overall_score,
            ),
            feedback=EvaluationFeedback(
                novelty_feedback=evaluation.novelty_feedback,
                structure_feedback=evaluation.structure_feedback,
                thoroughness_feedback=evaluation.thoroughness_feedback,
                clarity_feedback=evaluation.clarity_feedback,
                overall_summary=evaluation.overall_summary,
            ),
            novelty_analysis=NoveltyAnalysis(
                corpus_size=evaluation.novelty_comparison_count,
                most_similar_ebook_id=evaluation.most_similar_ebook_id,
                max_similarity_score=evaluation.max_similarity_score,
            ),
            judge_model=evaluation.judge_model,
            created_at=evaluation.created_at,
            completed_at=evaluation.completed_at,
        )
