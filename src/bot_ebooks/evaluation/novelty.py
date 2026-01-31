"""Novelty detection using vector embeddings and pgvector."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.ebook import Ebook, EbookStatus
from ..models.embedding import EMBEDDING_DIMENSION, EbookEmbedding

settings = get_settings()


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

    Uses a two-phase approach:
    1. Embedding-based similarity (fast, approximate)
    2. Theme extraction for context (lightweight)
    """

    def __init__(self, db: AsyncSession, openai_client: Optional[AsyncOpenAI] = None):
        self.db = db
        self.openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        self.top_n_compare = 5

    async def analyze(self, ebook: Ebook) -> NoveltyResult:
        """
        Analyze novelty of an ebook against the existing corpus.

        Args:
            ebook: The ebook to analyze

        Returns:
            NoveltyResult with similarity information
        """
        # Step 1: Generate embedding for the ebook
        embedding = await self.generate_embedding(ebook.content_markdown)

        # Step 2: Store the embedding
        await self._store_embedding(ebook.id, embedding)

        # Step 3: Find similar ebooks
        similar_ebooks = await self._find_similar(embedding, exclude_id=ebook.id)

        # Step 4: Get corpus size
        corpus_size = await self._get_corpus_size(exclude_id=ebook.id)

        if not similar_ebooks:
            return NoveltyResult(
                corpus_size=corpus_size,
                most_similar_id=None,
                most_similar_title=None,
                max_similarity=0.0,
                top_similar=[],
                overlapping_themes=[],
            )

        # Step 5: Extract overlapping themes from titles (simple approach)
        overlapping_themes = self._extract_themes_from_titles(
            ebook.title, [s["title"] for s in similar_ebooks[: self.top_n_compare]]
        )

        return NoveltyResult(
            corpus_size=corpus_size,
            most_similar_id=similar_ebooks[0]["ebook_id"],
            most_similar_title=similar_ebooks[0]["title"],
            max_similarity=similar_ebooks[0]["similarity"],
            top_similar=similar_ebooks[: self.top_n_compare],
            overlapping_themes=overlapping_themes,
        )

    async def generate_embedding(self, content: str) -> List[float]:
        """
        Generate embedding for content.

        For long content, chunks and averages embeddings.
        """
        # Chunk if too long (OpenAI limit is ~8000 tokens)
        max_chars = 30000  # Conservative estimate
        chunks = self._chunk_content(content, max_chars)

        embeddings = []
        for chunk in chunks:
            response = await self.openai.embeddings.create(
                model=self.embedding_model,
                input=chunk,
            )
            embeddings.append(response.data[0].embedding)

        # Average all chunk embeddings
        if len(embeddings) == 1:
            return embeddings[0]

        return np.mean(embeddings, axis=0).tolist()

    async def _store_embedding(self, ebook_id: UUID, embedding: List[float]) -> None:
        """Store embedding in the database."""
        # Check if already exists
        existing = await self.db.execute(
            select(EbookEmbedding).where(EbookEmbedding.ebook_id == ebook_id)
        )
        if existing.scalar_one_or_none():
            return

        ebook_embedding = EbookEmbedding(
            ebook_id=ebook_id,
            full_embedding=embedding,
            chunk_count=1,
            embedding_model=self.embedding_model,
            embedding_version="v1",
        )
        self.db.add(ebook_embedding)
        await self.db.flush()

    async def _find_similar(
        self,
        embedding: List[float],
        exclude_id: UUID,
        limit: int = 10,
    ) -> List[dict]:
        """
        Find most similar ebooks using cosine similarity via pgvector.
        """
        # pgvector query using <=> operator (cosine distance)
        # Similarity = 1 - distance
        query = (
            select(
                EbookEmbedding.ebook_id,
                Ebook.title,
                (1 - EbookEmbedding.full_embedding.cosine_distance(embedding)).label(
                    "similarity"
                ),
            )
            .join(Ebook, EbookEmbedding.ebook_id == Ebook.id)
            .where(EbookEmbedding.ebook_id != exclude_id)
            .where(Ebook.status == EbookStatus.PUBLISHED)
            .order_by(EbookEmbedding.full_embedding.cosine_distance(embedding))
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "ebook_id": row.ebook_id,
                "title": row.title,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    async def _get_corpus_size(self, exclude_id: Optional[UUID] = None) -> int:
        """Get total count of published ebooks with embeddings."""
        query = (
            select(func.count(EbookEmbedding.id))
            .join(Ebook, EbookEmbedding.ebook_id == Ebook.id)
            .where(Ebook.status == EbookStatus.PUBLISHED)
        )
        if exclude_id:
            query = query.where(EbookEmbedding.ebook_id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar() or 0

    def _chunk_content(self, content: str, max_chars: int) -> List[str]:
        """Split content into chunks for embedding."""
        if len(content) <= max_chars:
            return [content]

        chunks = []
        # Split by paragraphs/sections
        paragraphs = content.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else [content[:max_chars]]

    def _extract_themes_from_titles(
        self, new_title: str, similar_titles: List[str]
    ) -> List[str]:
        """
        Extract common themes from titles (simple keyword approach).

        For Phase 1, this is a simple word overlap approach.
        Future: Use LLM for more sophisticated theme extraction.
        """
        # Get words from new title
        new_words = set(
            word.lower()
            for word in new_title.split()
            if len(word) > 3 and word.isalpha()
        )

        # Find overlapping words in similar titles
        themes = set()
        for title in similar_titles:
            title_words = set(
                word.lower()
                for word in title.split()
                if len(word) > 3 and word.isalpha()
            )
            themes.update(new_words & title_words)

        # Filter out common words
        stopwords = {"the", "and", "for", "with", "from", "that", "this", "have", "been"}
        themes = themes - stopwords

        return list(themes)[:5]
