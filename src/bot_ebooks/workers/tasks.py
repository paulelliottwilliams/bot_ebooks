"""Background tasks for evaluation and other async operations.

This module provides both synchronous Celery tasks and async helper functions
for running evaluations. For Phase 1, we also provide a simple async runner
that can be triggered directly (useful for development and testing).

Supports three evaluation modes:
- efficient (default): Single Haiku call, ~8k tokens, ~46x cheaper
- single: Single Sonnet call with full prompts
- multi: Multiple providers/personas (most expensive)
"""

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..evaluation.efficient_judge import EfficientJudge
from ..evaluation.judge import LLMJudge
from ..evaluation.multi_judge import MultiLLMJudge
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import EvaluationStatus


async def run_evaluation(
    ebook_id: UUID,
    mode: str = "efficient",  # "efficient", "single", or "multi"
) -> dict:
    """
    Run evaluation for an ebook asynchronously.

    This is the core evaluation function that can be called directly
    or wrapped in a Celery task.

    Args:
        ebook_id: UUID of the ebook to evaluate
        mode: Evaluation mode:
            - "efficient" (default): Single Haiku call, ~8k tokens total
            - "single": Single Sonnet call with full prompts
            - "multi": Multiple providers/personas (most expensive)

    Returns:
        Dict with evaluation results

    Token usage comparison:
        - efficient: ~8,000 tokens per evaluation
        - single: ~40,000 tokens per evaluation
        - multi: ~380,000 tokens per evaluation (10 API calls)
    """
    async with AsyncSessionLocal() as db:
        # Get the ebook
        result = await db.execute(select(Ebook).where(Ebook.id == ebook_id))
        ebook = result.scalar_one_or_none()

        if not ebook:
            return {"error": f"Ebook {ebook_id} not found"}

        if ebook.status not in [EbookStatus.PENDING_EVALUATION, EbookStatus.EVALUATING]:
            return {"error": f"Ebook {ebook_id} is not pending evaluation"}

        # Select judge based on mode
        if mode == "multi":
            judge = MultiLLMJudge(db)
        elif mode == "single":
            judge = LLMJudge(db)
        else:  # "efficient" (default)
            judge = EfficientJudge(db)

        try:
            evaluation = await judge.evaluate_ebook(ebook)

            result_data = {
                "ebook_id": str(ebook_id),
                "status": evaluation.status.value,
                "overall_score": float(evaluation.overall_score)
                if evaluation.overall_score
                else None,
                "published": ebook.status == EbookStatus.PUBLISHED,
                "mode": mode,
            }

            # Add token usage if available (efficient judge tracks this)
            if evaluation.raw_llm_response:
                if "input_tokens" in evaluation.raw_llm_response:
                    result_data["input_tokens"] = evaluation.raw_llm_response["input_tokens"]
                    result_data["output_tokens"] = evaluation.raw_llm_response["output_tokens"]

            # Add multi-evaluator metadata if available
            if mode == "multi" and evaluation.evaluator_count:
                result_data["evaluator_count"] = evaluation.evaluator_count
                result_data["aggregation_method"] = evaluation.aggregation_method

            return result_data
        except Exception as e:
            return {
                "ebook_id": str(ebook_id),
                "status": "failed",
                "error": str(e),
            }


async def process_pending_evaluations(
    limit: int = 10,
    mode: str = "efficient",
) -> list[dict]:
    """
    Process all pending evaluations.

    Useful for batch processing or cron-triggered evaluation.

    Args:
        limit: Maximum number of evaluations to process
        mode: Evaluation mode ("efficient", "single", or "multi")

    Returns:
        List of evaluation results
    """
    async with AsyncSessionLocal() as db:
        # Get pending ebooks
        result = await db.execute(
            select(Ebook)
            .where(Ebook.status == EbookStatus.PENDING_EVALUATION)
            .limit(limit)
        )
        ebooks = result.scalars().all()

        results = []
        for ebook in ebooks:
            # Update status to evaluating
            ebook.status = EbookStatus.EVALUATING
            await db.commit()

            # Run evaluation
            eval_result = await run_evaluation(ebook.id, mode=mode)
            results.append(eval_result)

        return results


# Simple CLI for manual evaluation triggering
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m bot_ebooks.workers.tasks <ebook_id>")
        print("       python -m bot_ebooks.workers.tasks --pending")
        sys.exit(1)

    if sys.argv[1] == "--pending":
        results = asyncio.run(process_pending_evaluations())
        for r in results:
            print(r)
    else:
        ebook_id = UUID(sys.argv[1])
        result = asyncio.run(run_evaluation(ebook_id))
        print(result)
