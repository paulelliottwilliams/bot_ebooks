"""Novelty detection - currently disabled (requires pgvector).

This module is stubbed out because pgvector is not available on Railway's
default PostgreSQL. The novelty detection feature will return placeholder
values until pgvector is enabled.
"""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ebook import Ebook


@dataclass
class NoveltyResult:
    """Results from novelty analysis."""

    corpus_size: int
    most_similar_id: Optional[UUID]
    most_similar_title: Optional[str]
    max_similarity: float
    top_similar: List[dict]  # [{ebook_id, title, similarity}]
    overlapping_themes: List[str]


class NoveltyDetector:
    """
    Detects novelty of an ebook by comparing against the existing corpus.

    NOTE: Currently disabled - returns placeholder values.
    Requires pgvector extension to be enabled on PostgreSQL.
    """

    def __init__(self, db: AsyncSession, openai_client=None):
        self.db = db

    async def analyze(self, ebook: Ebook) -> NoveltyResult:
        """
        Analyze novelty of an ebook against the existing corpus.

        Currently returns placeholder values since pgvector is disabled.
        """
        return NoveltyResult(
            corpus_size=0,
            most_similar_id=None,
            most_similar_title=None,
            max_similarity=0.0,
            top_similar=[],
            overlapping_themes=[],
        )
