"""Evaluation API endpoints for triggering and checking evaluations."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from ..deps import DbSession, EbookServiceDep
from ...auth.api_keys import CurrentAgent
from ...models.ebook import EbookStatus
from ...workers.tasks import run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/{ebook_id}/trigger")
async def trigger_evaluation(
    ebook_id: UUID,
    agent: CurrentAgent,
    ebook_service: EbookServiceDep,
    background_tasks: BackgroundTasks,
):
    """
    Trigger evaluation for an ebook.

    Only the author can trigger evaluation for their ebooks.
    The ebook must be in pending_evaluation status.
    """
    ebook = await ebook_service.get_ebook_by_id(ebook_id)

    if not ebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ebook not found",
        )

    # Only author can trigger
    if ebook.author_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can trigger evaluation",
        )

    # Check status
    if ebook.status not in [EbookStatus.PENDING_EVALUATION, EbookStatus.EVALUATING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ebook is not pending evaluation (status: {ebook.status.value})",
        )

    # For Phase 1, we run evaluation in background task
    # In production, this would be a Celery task
    import asyncio

    async def run_in_background():
        await run_evaluation(ebook_id)

    background_tasks.add_task(asyncio.get_event_loop().run_until_complete, run_in_background())

    return {
        "message": "Evaluation triggered",
        "ebook_id": str(ebook_id),
        "status": "processing",
    }
