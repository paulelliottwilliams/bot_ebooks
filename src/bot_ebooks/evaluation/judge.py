"""LLM-Judge for evaluating ebook quality."""

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import Evaluation, EvaluationStatus
from .novelty import NoveltyDetector, NoveltyResult
from .prompts import JUDGE_EVALUATION_PROMPT, JUDGE_SYSTEM_PROMPT, build_novelty_context
from .rubrics import MINIMUM_OVERALL_SCORE, compute_overall_score

settings = get_settings()


class EvaluationError(Exception):
    """Raised when evaluation fails."""

    pass


class LLMJudge:
    """
    LLM-based judge for evaluating ebook quality.

    Orchestrates the full evaluation pipeline including novelty detection.
    """

    def __init__(
        self,
        db: AsyncSession,
        anthropic_client: Optional[AsyncAnthropic] = None,
        novelty_detector: Optional[NoveltyDetector] = None,
    ):
        self.db = db
        self.anthropic = anthropic_client or AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self.novelty_detector = novelty_detector or NoveltyDetector(db)
        self.model = settings.judge_model
        self.prompt_version = "v1.0"
        self.max_content_chars = 150000  # Approximately 37k tokens

    async def evaluate_ebook(self, ebook: Ebook) -> Evaluation:
        """
        Run full evaluation pipeline for an ebook.

        Steps:
        1. Update evaluation status to in_progress
        2. Run novelty detection
        3. Call LLM for evaluation
        4. Parse and store results
        5. Update ebook status based on score

        Returns:
            The completed Evaluation record
        """
        # Get or create evaluation record
        evaluation = await self._get_or_create_evaluation(ebook.id)

        try:
            # Update status to in_progress
            evaluation.status = EvaluationStatus.IN_PROGRESS
            evaluation.started_at = datetime.utcnow()
            await self.db.commit()

            # Step 1: Novelty detection
            novelty_result = await self.novelty_detector.analyze(ebook)

            # Step 2: Build prompt with novelty context
            novelty_context = build_novelty_context(
                corpus_size=novelty_result.corpus_size,
                most_similar_title=novelty_result.most_similar_title,
                max_similarity=novelty_result.max_similarity,
                overlapping_themes=novelty_result.overlapping_themes,
            )

            content = self._truncate_content(ebook.content_markdown)

            prompt = JUDGE_EVALUATION_PROMPT.format(
                title=ebook.title,
                category=ebook.category,
                word_count=ebook.word_count,
                novelty_context=novelty_context,
                content=content,
            )

            # Step 3: Call LLM
            response = await self.anthropic.messages.create(
                model=self.model,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )

            response_text = response.content[0].text

            # Step 4: Parse response
            scores = self._parse_evaluation_response(response_text)

            # Step 5: Compute overall score
            overall = compute_overall_score(
                {
                    "novelty": scores["novelty"]["score"],
                    "structure": scores["structure"]["score"],
                    "thoroughness": scores["thoroughness"]["score"],
                    "clarity": scores["clarity"]["score"],
                }
            )

            # Step 6: Update evaluation record
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.utcnow()

            evaluation.novelty_score = Decimal(str(scores["novelty"]["score"]))
            evaluation.structure_score = Decimal(str(scores["structure"]["score"]))
            evaluation.thoroughness_score = Decimal(str(scores["thoroughness"]["score"]))
            evaluation.clarity_score = Decimal(str(scores["clarity"]["score"]))
            evaluation.overall_score = overall

            evaluation.novelty_feedback = scores["novelty"]["feedback"]
            evaluation.structure_feedback = scores["structure"]["feedback"]
            evaluation.thoroughness_feedback = scores["thoroughness"]["feedback"]
            evaluation.clarity_feedback = scores["clarity"]["feedback"]
            evaluation.overall_summary = scores.get("overall_summary", "")

            evaluation.novelty_comparison_count = novelty_result.corpus_size
            evaluation.most_similar_ebook_id = novelty_result.most_similar_id
            evaluation.max_similarity_score = (
                Decimal(str(novelty_result.max_similarity))
                if novelty_result.max_similarity
                else None
            )

            evaluation.judge_model = self.model
            evaluation.judge_prompt_version = self.prompt_version
            evaluation.raw_llm_response = {"response": response_text}

            # Step 7: Update ebook status
            if overall >= MINIMUM_OVERALL_SCORE:
                ebook.status = EbookStatus.PUBLISHED
                ebook.published_at = datetime.utcnow()
            else:
                ebook.status = EbookStatus.REJECTED

            await self.db.commit()
            await self.db.refresh(evaluation)

            return evaluation

        except Exception as e:
            # Mark evaluation as failed
            evaluation.status = EvaluationStatus.FAILED
            evaluation.error_message = str(e)
            evaluation.completed_at = datetime.utcnow()
            ebook.status = EbookStatus.REJECTED
            await self.db.commit()
            raise EvaluationError(f"Evaluation failed: {e}") from e

    async def _get_or_create_evaluation(self, ebook_id) -> Evaluation:
        """Get existing evaluation or create new one."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(Evaluation).where(Evaluation.ebook_id == ebook_id)
        )
        evaluation = result.scalar_one_or_none()

        if not evaluation:
            evaluation = Evaluation(
                ebook_id=ebook_id,
                status=EvaluationStatus.PENDING,
            )
            self.db.add(evaluation)
            await self.db.flush()

        return evaluation

    def _truncate_content(self, content: str) -> str:
        """
        Truncate content if too long, preserving structure.

        Keeps beginning and end, samples from middle.
        """
        if len(content) <= self.max_content_chars:
            return content

        # Keep first 50%, last 20%, sample from middle
        intro_len = int(self.max_content_chars * 0.5)
        conclusion_len = int(self.max_content_chars * 0.2)
        middle_len = self.max_content_chars - intro_len - conclusion_len

        intro = content[:intro_len]
        conclusion = content[-conclusion_len:]

        # Sample from middle
        middle_start = len(content) // 3
        middle = content[middle_start : middle_start + middle_len]

        return (
            f"{intro}\n\n"
            f"[... content truncated for evaluation ({len(content):,} chars total) ...]\n\n"
            f"{middle}\n\n"
            f"[... content truncated ...]\n\n"
            f"{conclusion}"
        )

    def _parse_evaluation_response(self, response_text: str) -> dict:
        """
        Parse the LLM's JSON response into scores and feedback.

        Handles various JSON formatting issues.
        """
        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            raise EvaluationError("No JSON found in LLM response")

        json_str = json_match.group()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise EvaluationError(f"Invalid JSON in LLM response: {e}")

        # Validate required fields
        required_dims = ["novelty", "structure", "thoroughness", "clarity"]
        for dim in required_dims:
            if dim not in data:
                raise EvaluationError(f"Missing dimension in response: {dim}")
            if "score" not in data[dim]:
                raise EvaluationError(f"Missing score for dimension: {dim}")
            if "feedback" not in data[dim]:
                data[dim]["feedback"] = ""

            # Validate score range
            score = float(data[dim]["score"])
            if not 1 <= score <= 10:
                raise EvaluationError(
                    f"Score for {dim} out of range: {score} (must be 1-10)"
                )

        return data
