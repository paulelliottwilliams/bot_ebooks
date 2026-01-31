"""Aggregation methods for combining multiple evaluator scores.

Combines scores from multiple (provider, persona) pairs into a final
evaluation score using various strategies.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional
import statistics


class AggregationMethod(str, Enum):
    """Methods for aggregating multiple evaluator scores."""

    MEAN = "mean"
    MEDIAN = "median"
    TRIMMED_MEAN = "trimmed_mean"  # Drop highest and lowest
    WEIGHTED_MEAN = "weighted_mean"  # Weight by persona strictness


@dataclass
class IndividualScore:
    """Score from a single evaluator (provider + persona)."""

    provider: str
    persona_id: str
    novelty_score: Decimal
    structure_score: Decimal
    thoroughness_score: Decimal
    clarity_score: Decimal
    weighted_score: Decimal
    success: bool

    def to_float_dict(self) -> Dict[str, float]:
        """Convert scores to floats for statistical operations."""
        return {
            "novelty": float(self.novelty_score),
            "structure": float(self.structure_score),
            "thoroughness": float(self.thoroughness_score),
            "clarity": float(self.clarity_score),
            "weighted": float(self.weighted_score),
        }


@dataclass
class AggregatedScore:
    """Final aggregated scores from multiple evaluators."""

    novelty_score: Decimal
    structure_score: Decimal
    thoroughness_score: Decimal
    clarity_score: Decimal
    overall_score: Decimal

    # Metadata about the aggregation
    evaluator_count: int
    successful_count: int
    method: AggregationMethod

    # Agreement metrics
    score_std_dev: float  # Standard deviation of weighted scores
    max_disagreement: float  # Largest gap between any two evaluators

    # Which evaluators contributed
    evaluator_breakdown: List[Dict]


def aggregate_scores(
    individual_scores: List[IndividualScore],
    method: AggregationMethod = AggregationMethod.MEDIAN,
) -> AggregatedScore:
    """
    Aggregate multiple individual evaluations into a final score.

    Args:
        individual_scores: List of scores from individual evaluators
        method: How to combine the scores

    Returns:
        Aggregated final score with metadata
    """
    # Filter to successful evaluations only
    successful = [s for s in individual_scores if s.success]

    if not successful:
        raise ValueError("No successful evaluations to aggregate")

    # Extract score lists for each dimension
    novelty_scores = [float(s.novelty_score) for s in successful]
    structure_scores = [float(s.structure_score) for s in successful]
    thoroughness_scores = [float(s.thoroughness_score) for s in successful]
    clarity_scores = [float(s.clarity_score) for s in successful]
    weighted_scores = [float(s.weighted_score) for s in successful]

    # Aggregate based on method
    if method == AggregationMethod.MEAN:
        agg_novelty = statistics.mean(novelty_scores)
        agg_structure = statistics.mean(structure_scores)
        agg_thoroughness = statistics.mean(thoroughness_scores)
        agg_clarity = statistics.mean(clarity_scores)
        agg_overall = statistics.mean(weighted_scores)

    elif method == AggregationMethod.MEDIAN:
        agg_novelty = statistics.median(novelty_scores)
        agg_structure = statistics.median(structure_scores)
        agg_thoroughness = statistics.median(thoroughness_scores)
        agg_clarity = statistics.median(clarity_scores)
        agg_overall = statistics.median(weighted_scores)

    elif method == AggregationMethod.TRIMMED_MEAN:
        # Drop highest and lowest if we have enough evaluators
        if len(successful) >= 4:
            agg_novelty = _trimmed_mean(novelty_scores)
            agg_structure = _trimmed_mean(structure_scores)
            agg_thoroughness = _trimmed_mean(thoroughness_scores)
            agg_clarity = _trimmed_mean(clarity_scores)
            agg_overall = _trimmed_mean(weighted_scores)
        else:
            # Fall back to median for small samples
            agg_novelty = statistics.median(novelty_scores)
            agg_structure = statistics.median(structure_scores)
            agg_thoroughness = statistics.median(thoroughness_scores)
            agg_clarity = statistics.median(clarity_scores)
            agg_overall = statistics.median(weighted_scores)

    elif method == AggregationMethod.WEIGHTED_MEAN:
        # Weight by inverse of persona strictness (give harsher reviewers less weight)
        # This helps normalize across different evaluation styles
        from .personas import get_persona

        weights = []
        for s in successful:
            try:
                persona = get_persona(s.persona_id)
                # Inverse strictness: lenient reviewers get higher weight
                weight = 1.0 - (persona.strictness * 0.3)  # Scale down impact
            except ValueError:
                weight = 1.0
            weights.append(weight)

        total_weight = sum(weights)
        agg_novelty = sum(s * w for s, w in zip(novelty_scores, weights)) / total_weight
        agg_structure = sum(s * w for s, w in zip(structure_scores, weights)) / total_weight
        agg_thoroughness = sum(s * w for s, w in zip(thoroughness_scores, weights)) / total_weight
        agg_clarity = sum(s * w for s, w in zip(clarity_scores, weights)) / total_weight
        agg_overall = sum(s * w for s, w in zip(weighted_scores, weights)) / total_weight
    else:
        raise ValueError(f"Unknown aggregation method: {method}")

    # Calculate agreement metrics
    score_std_dev = statistics.stdev(weighted_scores) if len(weighted_scores) > 1 else 0.0
    max_disagreement = max(weighted_scores) - min(weighted_scores) if weighted_scores else 0.0

    # Build breakdown of contributors
    evaluator_breakdown = [
        {
            "provider": s.provider,
            "persona": s.persona_id,
            "weighted_score": float(s.weighted_score),
        }
        for s in successful
    ]

    return AggregatedScore(
        novelty_score=Decimal(str(round(agg_novelty, 2))),
        structure_score=Decimal(str(round(agg_structure, 2))),
        thoroughness_score=Decimal(str(round(agg_thoroughness, 2))),
        clarity_score=Decimal(str(round(agg_clarity, 2))),
        overall_score=Decimal(str(round(agg_overall, 2))),
        evaluator_count=len(individual_scores),
        successful_count=len(successful),
        method=method,
        score_std_dev=round(score_std_dev, 3),
        max_disagreement=round(max_disagreement, 2),
        evaluator_breakdown=evaluator_breakdown,
    )


def _trimmed_mean(values: List[float]) -> float:
    """Calculate mean after removing highest and lowest values."""
    if len(values) <= 2:
        return statistics.mean(values)

    sorted_values = sorted(values)
    trimmed = sorted_values[1:-1]  # Remove first and last
    return statistics.mean(trimmed)


def generate_consensus_summary(
    individual_scores: List[IndividualScore],
    aggregated: AggregatedScore,
) -> str:
    """
    Generate a human-readable summary of evaluator agreement/disagreement.

    Useful for transparency about how confident we are in the final score.
    """
    successful = [s for s in individual_scores if s.success]

    if not successful:
        return "No successful evaluations."

    lines = [
        f"Evaluation based on {aggregated.successful_count} of {aggregated.evaluator_count} evaluators.",
        f"Aggregation method: {aggregated.method.value}",
        f"",
        f"Final overall score: {aggregated.overall_score}",
        f"Score standard deviation: {aggregated.score_std_dev:.2f}",
        f"Max disagreement: {aggregated.max_disagreement:.1f} points",
    ]

    # Characterize agreement level
    if aggregated.max_disagreement <= 1.0:
        agreement = "Strong agreement"
    elif aggregated.max_disagreement <= 2.0:
        agreement = "Moderate agreement"
    elif aggregated.max_disagreement <= 3.0:
        agreement = "Some disagreement"
    else:
        agreement = "Significant disagreement"

    lines.append(f"Consensus level: {agreement}")
    lines.append("")

    # Individual breakdown
    lines.append("Individual evaluator scores:")
    for item in aggregated.evaluator_breakdown:
        lines.append(f"  - {item['provider']}/{item['persona']}: {item['weighted_score']:.2f}")

    return "\n".join(lines)
