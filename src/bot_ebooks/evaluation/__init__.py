"""Evaluation system for LLM-Judge and novelty detection."""

from .judge import LLMJudge
from .multi_judge import MultiLLMJudge
from .novelty import NoveltyDetector
from .rubrics import EVALUATION_DIMENSIONS
from .personas import EvaluatorPersona, PERSONAS, get_persona, get_default_personas
from .providers import LLMProvider, get_provider, get_available_providers
from .aggregation import AggregationMethod, aggregate_scores

__all__ = [
    "LLMJudge",
    "MultiLLMJudge",
    "NoveltyDetector",
    "EVALUATION_DIMENSIONS",
    "EvaluatorPersona",
    "PERSONAS",
    "get_persona",
    "get_default_personas",
    "LLMProvider",
    "get_provider",
    "get_available_providers",
    "AggregationMethod",
    "aggregate_scores",
]
