"""Evaluation rubrics defining the four quality dimensions."""

from decimal import Decimal

# Weights for each dimension (must sum to 1.0)
EVALUATION_DIMENSIONS = {
    "novelty": {
        "weight": Decimal("0.30"),
        "description": "Originality and uniqueness of ideas, arguments, or perspectives",
        "criteria": {
            10: "Presents genuinely original thesis or framework not seen in existing corpus. Introduces novel connections between concepts.",
            8: "Offers fresh perspective on familiar topics. Contains several original insights or arguments.",
            6: "Competent synthesis of existing ideas with some original observations. Adequate differentiation from similar works.",
            4: "Mostly derivative. Retreads familiar ground with minimal new contribution.",
            2: "Highly derivative or near-duplicate of existing corpus content.",
            1: "Plagiarism or direct copy of existing work.",
        },
    },
    "structure": {
        "weight": Decimal("0.20"),
        "description": "Organization, logical flow, and coherent presentation",
        "criteria": {
            10: "Masterful organization. Clear thesis, logical progression, effective transitions, satisfying conclusion. Each section builds purposefully.",
            8: "Well-organized with clear sections. Arguments flow logically. Minor structural improvements possible.",
            6: "Adequate structure. Main points identifiable but some disorganization or awkward transitions.",
            4: "Weak organization. Difficult to follow argument progression. Missing key structural elements.",
            2: "Severely disorganized. No clear thesis or logical flow. Reads as disconnected fragments.",
            1: "No discernible structure. Stream of consciousness or incoherent.",
        },
    },
    "thoroughness": {
        "weight": Decimal("0.30"),
        "description": "Depth of research, evidence quality, and comprehensive coverage",
        "criteria": {
            10: "Exhaustive coverage of topic. Multiple perspectives examined. Claims well-supported with specific evidence. Addresses counterarguments.",
            8: "Comprehensive treatment. Good evidence base. Covers major aspects thoroughly with some depth.",
            6: "Adequate depth. Covers main points with reasonable support. Some gaps in coverage or evidence.",
            4: "Superficial treatment. Claims lack adequate support. Major aspects of topic missing.",
            2: "Very shallow. Mostly unsupported assertions. Minimal research evident.",
            1: "No substantive content. Empty or trivial.",
        },
    },
    "clarity": {
        "weight": Decimal("0.20"),
        "description": "Writing quality, readability, and effective communication",
        "criteria": {
            10: "Exceptionally clear prose. Complex ideas explained accessibly. Precise language. Engaging to read.",
            8: "Clear and readable. Good explanations. Minor areas where clarity could improve.",
            6: "Generally understandable. Some unclear passages or jargon. Adequate communication of ideas.",
            4: "Frequently unclear. Poor explanations. Excessive jargon or convoluted sentences.",
            2: "Very difficult to understand. Major communication failures throughout.",
            1: "Incomprehensible. Cannot extract meaning.",
        },
    },
}

# Minimum threshold for publication
MINIMUM_OVERALL_SCORE = Decimal("3.0")


def compute_overall_score(scores: dict) -> Decimal:
    """
    Compute weighted average of dimension scores.

    Args:
        scores: Dict with keys novelty, structure, thoroughness, clarity
                and Decimal values

    Returns:
        Weighted overall score as Decimal
    """
    total = Decimal("0")
    for dim, config in EVALUATION_DIMENSIONS.items():
        if dim in scores and scores[dim] is not None:
            total += Decimal(str(scores[dim])) * config["weight"]
    return total.quantize(Decimal("0.01"))


def format_rubric_for_prompt() -> str:
    """Format the rubrics for inclusion in the LLM prompt."""
    lines = []
    for dim, config in EVALUATION_DIMENSIONS.items():
        lines.append(f"\n## {dim.upper()} ({int(config['weight'] * 100)}% weight)")
        lines.append(f"{config['description']}\n")
        lines.append("Scoring guide:")
        for score, description in sorted(config["criteria"].items(), reverse=True):
            lines.append(f"  {score}: {description}")
    return "\n".join(lines)
