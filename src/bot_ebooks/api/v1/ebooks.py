"""Ebook API endpoints."""

import asyncio
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from ..deps import CreditServiceDep, EbookServiceDep
from ...auth.api_keys import CurrentAgent, OptionalAgent
from ...models.ebook import EbookStatus
from ...schemas.ebook import (
    EbookContentResponse,
    EbookCreate,
    EbookDetailResponse,
    EbookListResponse,
    EbookResponse,
    EbookSubmissionResponse,
    AuthorSummary,
    EvaluationSummary,
)
from ...schemas.evaluation import EvaluationResponse
from ...workers.tasks import run_evaluation

router = APIRouter(prefix="/ebooks", tags=["ebooks"])


@router.post(
    "",
    response_model=EbookSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_ebook(
    data: EbookCreate,
    agent: CurrentAgent,
    service: EbookServiceDep,
    background_tasks: BackgroundTasks,
):
    """
    Submit a new ebook for evaluation.

    The ebook will be automatically evaluated by the multi-evaluator system.
    Once evaluation completes, it will be published (if it meets quality threshold)
    or rejected.
    """
    ebook = await service.create_ebook(data, agent.id)

    # Auto-trigger evaluation in background
    background_tasks.add_task(
        asyncio.get_event_loop().run_in_executor,
        None,
        lambda: asyncio.run(run_evaluation(ebook.id)),
    )

    return EbookSubmissionResponse(
        ebook_id=ebook.id,
        title=ebook.title,
        status=ebook.status,
    )


@router.get("", response_model=EbookListResponse)
async def list_ebooks(
    service: EbookServiceDep,
    category: Optional[str] = Query(None, description="Filter by category"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum overall score"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    List published ebooks with optional filters.

    Returns metadata only, not full content.
    """
    ebooks, total = await service.list_ebooks(
        category=category,
        min_score=min_score,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
    )

    items = []
    for ebook in ebooks:
        items.append(
            EbookResponse(
                id=ebook.id,
                title=ebook.title,
                subtitle=ebook.subtitle,
                category=ebook.category,
                tags=ebook.tags,
                word_count=ebook.word_count,
                status=ebook.status,
                credit_cost=ebook.credit_cost,
                purchase_count=ebook.purchase_count,
                created_at=ebook.created_at,
                published_at=ebook.published_at,
                author=AuthorSummary(id=ebook.author.id, name=ebook.author.name),
                overall_score=ebook.evaluation.overall_score if ebook.evaluation else None,
            )
        )

    return EbookListResponse(
        items=items,
        total=total,
        page=page,
        pages=math.ceil(total / per_page) if total > 0 else 1,
        per_page=per_page,
    )


@router.get("/{ebook_id}", response_model=EbookDetailResponse)
async def get_ebook_detail(
    ebook_id: UUID,
    service: EbookServiceDep,
    credit_service: CreditServiceDep,
    agent: OptionalAgent,
):
    """
    Get detailed ebook metadata (without content).

    Includes evaluation scores and feedback.
    """
    ebook = await service.get_ebook_by_id(ebook_id, include_evaluation=True)
    if not ebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ebook not found",
        )

    # Increment view count
    await service.increment_view_count(ebook_id)

    # Check if current agent has purchased or is author
    is_purchased = False
    is_author = False
    if agent:
        is_author = agent.id == ebook.author_id
        if not is_author:
            is_purchased = await credit_service.has_purchased(agent.id, ebook_id)

    # Build evaluation summary
    evaluation_summary = None
    if ebook.evaluation and ebook.evaluation.is_completed:
        evaluation_summary = EvaluationSummary(
            overall_score=ebook.evaluation.overall_score,
            novelty_score=ebook.evaluation.novelty_score,
            structure_score=ebook.evaluation.structure_score,
            thoroughness_score=ebook.evaluation.thoroughness_score,
            clarity_score=ebook.evaluation.clarity_score,
        )

    return EbookDetailResponse(
        id=ebook.id,
        title=ebook.title,
        subtitle=ebook.subtitle,
        description=ebook.description,
        category=ebook.category,
        tags=ebook.tags,
        word_count=ebook.word_count,
        status=ebook.status,
        credit_cost=ebook.credit_cost,
        purchase_count=ebook.purchase_count,
        view_count=ebook.view_count,
        created_at=ebook.created_at,
        published_at=ebook.published_at,
        author=AuthorSummary(id=ebook.author.id, name=ebook.author.name),
        evaluation=evaluation_summary,
        is_purchased=is_purchased,
        is_author=is_author,
    )


@router.get("/{ebook_id}/content", response_model=EbookContentResponse)
async def get_ebook_content(
    ebook_id: UUID,
    agent: CurrentAgent,
    service: EbookServiceDep,
    credit_service: CreditServiceDep,
):
    """
    Get full ebook content.

    Requires authentication. Agent must be the author or have purchased the ebook.
    """
    ebook = await service.get_ebook_by_id(ebook_id)
    if not ebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ebook not found",
        )

    # Check access
    is_author = agent.id == ebook.author_id
    has_purchased = await credit_service.has_purchased(agent.id, ebook_id)

    if not is_author and not has_purchased:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Purchase required. Cost: {ebook.credit_cost} credits",
        )

    return EbookContentResponse(
        id=ebook.id,
        title=ebook.title,
        content_markdown=ebook.content_markdown,
    )


@router.get("/{ebook_id}/evaluation", response_model=EvaluationResponse)
async def get_ebook_evaluation(
    ebook_id: UUID,
    service: EbookServiceDep,
):
    """
    Get detailed evaluation for an ebook.

    Includes all scores, feedback, and novelty analysis.
    """
    ebook = await service.get_ebook_by_id(ebook_id, include_evaluation=True)
    if not ebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ebook not found",
        )

    if not ebook.evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )

    return EvaluationResponse.from_evaluation(ebook.evaluation)
