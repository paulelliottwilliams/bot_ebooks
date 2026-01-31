"""Ebook service for business logic."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..models.agent import Agent
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import Evaluation, EvaluationStatus
from ..schemas.ebook import EbookCreate

settings = get_settings()


class EbookService:
    """Service for ebook-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ebook(self, data: EbookCreate, author_id: UUID) -> Ebook:
        """
        Create a new ebook and queue it for evaluation.

        Returns:
            The created ebook (status: pending_evaluation)
        """
        # Calculate word count
        word_count = self._count_words(data.content_markdown)

        # Create ebook
        ebook = Ebook(
            title=data.title,
            subtitle=data.subtitle,
            description=data.description,
            category=data.category,
            tags=data.tags,
            content_markdown=data.content_markdown,
            word_count=word_count,
            author_id=author_id,
            status=EbookStatus.PENDING_EVALUATION,
            credit_cost=settings.ebook_price,
        )
        self.db.add(ebook)
        await self.db.flush()

        # Create pending evaluation record
        evaluation = Evaluation(
            ebook_id=ebook.id,
            status=EvaluationStatus.PENDING,
        )
        self.db.add(evaluation)

        await self.db.commit()
        await self.db.refresh(ebook)

        return ebook

    async def get_ebook_by_id(
        self,
        ebook_id: UUID,
        include_evaluation: bool = True,
    ) -> Optional[Ebook]:
        """Get ebook by ID, optionally including evaluation."""
        query = select(Ebook).where(Ebook.id == ebook_id).options(
            selectinload(Ebook.author)
        )

        if include_evaluation:
            query = query.options(selectinload(Ebook.evaluation))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_ebooks(
        self,
        category: Optional[str] = None,
        min_score: Optional[float] = None,
        status: Optional[EbookStatus] = None,
        author_id: Optional[UUID] = None,
        search_query: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Ebook], int]:
        """
        List ebooks with filters and pagination.

        Returns:
            Tuple of (ebooks, total_count)
        """
        # Base query for published ebooks
        query = (
            select(Ebook)
            .options(selectinload(Ebook.author), selectinload(Ebook.evaluation))
        )

        # Default to published only unless author_id provided
        if status:
            query = query.where(Ebook.status == status)
        elif not author_id:
            query = query.where(Ebook.status == EbookStatus.PUBLISHED)

        # Apply filters
        if category:
            query = query.where(Ebook.category == category.lower())

        if author_id:
            query = query.where(Ebook.author_id == author_id)

        if search_query:
            search_term = f"%{search_query}%"
            query = query.where(
                or_(
                    Ebook.title.ilike(search_term),
                    Ebook.description.ilike(search_term),
                )
            )

        if min_score is not None:
            query = query.join(Evaluation).where(
                Evaluation.overall_score >= min_score
            )

        # Count total before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = self._get_sort_column(sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.limit(per_page).offset(offset)

        result = await self.db.execute(query)
        ebooks = list(result.scalars().all())

        return ebooks, total

    async def increment_view_count(self, ebook_id: UUID) -> None:
        """Increment the view count for an ebook."""
        ebook = await self.db.get(Ebook, ebook_id)
        if ebook:
            ebook.view_count += 1
            await self.db.commit()

    async def publish_ebook(self, ebook_id: UUID) -> Optional[Ebook]:
        """Mark an ebook as published after successful evaluation."""
        ebook = await self.db.get(Ebook, ebook_id)
        if ebook:
            ebook.status = EbookStatus.PUBLISHED
            ebook.published_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(ebook)
        return ebook

    async def reject_ebook(self, ebook_id: UUID) -> Optional[Ebook]:
        """Mark an ebook as rejected after failed evaluation."""
        ebook = await self.db.get(Ebook, ebook_id)
        if ebook:
            ebook.status = EbookStatus.REJECTED
            await self.db.commit()
            await self.db.refresh(ebook)
        return ebook

    async def get_corpus_size(self, exclude_id: Optional[UUID] = None) -> int:
        """Get total count of published ebooks (for novelty comparison)."""
        query = select(func.count(Ebook.id)).where(
            Ebook.status == EbookStatus.PUBLISHED
        )
        if exclude_id:
            query = query.where(Ebook.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar() or 0

    def _count_words(self, content: str) -> int:
        """Count words in markdown content."""
        # Remove markdown syntax
        text = re.sub(r"[#*`\[\](){}|>]", " ", content)
        # Remove URLs
        text = re.sub(r"https?://\S+", " ", text)
        # Split and count non-empty words
        words = [w for w in text.split() if w.strip()]
        return len(words)

    def _get_sort_column(self, sort_by: str):
        """Get SQLAlchemy column for sorting."""
        columns = {
            "created_at": Ebook.created_at,
            "published_at": Ebook.published_at,
            "title": Ebook.title,
            "purchase_count": Ebook.purchase_count,
            "word_count": Ebook.word_count,
        }
        return columns.get(sort_by, Ebook.created_at)
