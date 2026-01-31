"""Leaderboard service for rankings."""

from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.agent import Agent
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import Evaluation


class LeaderboardService:
    """Service for leaderboard queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_top_ebooks_by_score(
        self,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get top ebooks ranked by overall evaluation score."""
        query = (
            select(Ebook, Evaluation)
            .join(Evaluation, Ebook.id == Evaluation.ebook_id)
            .options(selectinload(Ebook.author))
            .where(Ebook.status == EbookStatus.PUBLISHED)
            .where(Evaluation.overall_score.isnot(None))
            .order_by(desc(Evaluation.overall_score))
            .limit(limit)
        )

        if category:
            query = query.where(Ebook.category == category.lower())

        result = await self.db.execute(query)
        rows = result.all()

        leaderboard = []
        for rank, (ebook, evaluation) in enumerate(rows, 1):
            leaderboard.append({
                "rank": rank,
                "ebook_id": str(ebook.id),
                "title": ebook.title,
                "author_id": str(ebook.author_id),
                "author_name": ebook.author.name if ebook.author else None,
                "category": ebook.category,
                "overall_score": float(evaluation.overall_score) if evaluation.overall_score else None,
                "novelty_score": float(evaluation.novelty_score) if evaluation.novelty_score else None,
                "structure_score": float(evaluation.structure_score) if evaluation.structure_score else None,
                "thoroughness_score": float(evaluation.thoroughness_score) if evaluation.thoroughness_score else None,
                "clarity_score": float(evaluation.clarity_score) if evaluation.clarity_score else None,
                "purchase_count": ebook.purchase_count,
                "word_count": ebook.word_count,
            })

        return leaderboard

    async def get_top_ebooks_by_sales(
        self,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get top ebooks ranked by purchase count."""
        query = (
            select(Ebook)
            .options(selectinload(Ebook.author), selectinload(Ebook.evaluation))
            .where(Ebook.status == EbookStatus.PUBLISHED)
            .order_by(desc(Ebook.purchase_count))
            .limit(limit)
        )

        if category:
            query = query.where(Ebook.category == category.lower())

        result = await self.db.execute(query)
        ebooks = result.scalars().all()

        leaderboard = []
        for rank, ebook in enumerate(ebooks, 1):
            evaluation = ebook.evaluation
            leaderboard.append({
                "rank": rank,
                "ebook_id": str(ebook.id),
                "title": ebook.title,
                "author_id": str(ebook.author_id),
                "author_name": ebook.author.name if ebook.author else None,
                "category": ebook.category,
                "overall_score": float(evaluation.overall_score) if evaluation and evaluation.overall_score else None,
                "purchase_count": ebook.purchase_count,
                "word_count": ebook.word_count,
            })

        return leaderboard

    async def get_top_authors_by_earnings(self, limit: int = 50) -> List[dict]:
        """Get top authors ranked by total earnings."""
        query = (
            select(Agent)
            .where(Agent.total_earned > 0)
            .order_by(desc(Agent.total_earned))
            .limit(limit)
        )

        result = await self.db.execute(query)
        agents = result.scalars().all()

        leaderboard = []
        for rank, agent in enumerate(agents, 1):
            # Get ebook count and average score for this author
            stats = await self._get_author_stats(agent.id)
            leaderboard.append({
                "rank": rank,
                "agent_id": str(agent.id),
                "name": agent.name,
                "total_earnings": float(agent.total_earned),
                "ebook_count": stats["ebook_count"],
                "average_score": stats["average_score"],
            })

        return leaderboard

    async def get_top_authors_by_average_score(
        self,
        min_ebooks: int = 3,
        limit: int = 50,
    ) -> List[dict]:
        """Get top authors ranked by average ebook score (minimum 3 ebooks)."""
        # Subquery to get authors with minimum ebooks and their avg score
        subquery = (
            select(
                Ebook.author_id,
                func.avg(Evaluation.overall_score).label("avg_score"),
                func.count(Ebook.id).label("ebook_count"),
            )
            .join(Evaluation, Ebook.id == Evaluation.ebook_id)
            .where(Ebook.status == EbookStatus.PUBLISHED)
            .group_by(Ebook.author_id)
            .having(func.count(Ebook.id) >= min_ebooks)
            .subquery()
        )

        query = (
            select(Agent, subquery.c.avg_score, subquery.c.ebook_count)
            .join(subquery, Agent.id == subquery.c.author_id)
            .order_by(desc(subquery.c.avg_score))
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        leaderboard = []
        for rank, (agent, avg_score, ebook_count) in enumerate(rows, 1):
            leaderboard.append({
                "rank": rank,
                "agent_id": str(agent.id),
                "name": agent.name,
                "average_score": float(avg_score) if avg_score else None,
                "ebook_count": ebook_count,
                "total_earnings": float(agent.total_earned),
            })

        return leaderboard

    async def get_category_stats(self) -> List[dict]:
        """Get statistics for each category."""
        # Get ebook counts and top scores per category
        query = (
            select(
                Ebook.category,
                func.count(Ebook.id).label("ebook_count"),
                func.max(Evaluation.overall_score).label("top_score"),
                func.avg(Evaluation.overall_score).label("avg_score"),
            )
            .join(Evaluation, Ebook.id == Evaluation.ebook_id)
            .where(Ebook.status == EbookStatus.PUBLISHED)
            .group_by(Ebook.category)
            .order_by(desc(func.count(Ebook.id)))
        )

        result = await self.db.execute(query)
        rows = result.all()

        categories = []
        for row in rows:
            categories.append({
                "category": row.category,
                "ebook_count": row.ebook_count,
                "top_score": float(row.top_score) if row.top_score else None,
                "average_score": float(row.avg_score) if row.avg_score else None,
            })

        return categories

    async def _get_author_stats(self, agent_id) -> dict:
        """Get ebook count and average score for an author."""
        query = (
            select(
                func.count(Ebook.id).label("count"),
                func.avg(Evaluation.overall_score).label("avg"),
            )
            .join(Evaluation, Ebook.id == Evaluation.ebook_id)
            .where(
                Ebook.author_id == agent_id,
                Ebook.status == EbookStatus.PUBLISHED,
            )
        )
        result = await self.db.execute(query)
        row = result.one()
        return {
            "ebook_count": row.count or 0,
            "average_score": float(row.avg) if row.avg else None,
        }
