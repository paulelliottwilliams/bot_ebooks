"""Leaderboard API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Query

from ..deps import LeaderboardServiceDep

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/ebooks")
async def get_ebook_leaderboard(
    service: LeaderboardServiceDep,
    category: Optional[str] = Query(None, description="Filter by category"),
    metric: str = Query("score", pattern="^(score|sales)$", description="Ranking metric"),
    limit: int = Query(50, ge=1, le=100),
) -> List[dict]:
    """
    Get top ebooks ranked by score or sales.
    """
    if metric == "score":
        return await service.get_top_ebooks_by_score(category=category, limit=limit)
    else:
        return await service.get_top_ebooks_by_sales(category=category, limit=limit)


@router.get("/authors")
async def get_author_leaderboard(
    service: LeaderboardServiceDep,
    metric: str = Query(
        "earnings",
        pattern="^(earnings|average_score)$",
        description="Ranking metric",
    ),
    limit: int = Query(50, ge=1, le=100),
) -> List[dict]:
    """
    Get top authors ranked by earnings or average score.

    For average_score, only authors with 3+ published ebooks are included.
    """
    if metric == "earnings":
        return await service.get_top_authors_by_earnings(limit=limit)
    else:
        return await service.get_top_authors_by_average_score(limit=limit)


@router.get("/categories")
async def get_category_stats(
    service: LeaderboardServiceDep,
) -> List[dict]:
    """
    Get statistics for each category.

    Includes ebook count, top score, and average score per category.
    """
    return await service.get_category_stats()
