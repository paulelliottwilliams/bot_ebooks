"""Multi-evaluator LLM Judge system.

Orchestrates evaluation across multiple LLM providers and evaluator personas,
then aggregates results into a final score.
"""

import asyncio
import time
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import Evaluation, EvaluationStatus
from ..models.individual_evaluation import IndividualEvaluation
from .aggregation import (
    AggregatedScore,
    AggregationMethod,
    IndividualScore,
    aggregate_scores,
    generate_consensus_summary,
)
from .novelty import NoveltyDetector, NoveltyResult
from .personas import EvaluatorPersona, get_default_personas, get_persona
from .prompts import JUDGE_EVALUATION_PROMPT, build_novelty_context
from .providers import LLMProvider, get_available_providers, get_provider
from .rubrics import MINIMUM_OVERALL_SCORE, format_rubric_for_prompt

settings = get_settings()


class MultiEvaluationError(Exception):
    """Raised when multi-evaluation fails."""
    pass


def build_persona_system_prompt(persona: EvaluatorPersona) -> str:
    """Build a system prompt customized for a specific persona."""
    return f"""You are an expert literary critic and academic reviewer evaluating non-fiction ebooks for the bot_ebooks marketplace. Your role is to provide fair, consistent, and constructive evaluations.

## Your Evaluator Persona: {persona.name}

{persona.description}

{persona.evaluation_guidance}

## Evaluation Dimensions

You will evaluate each ebook on four dimensions with the following weights for YOUR scoring:
- **Novelty** ({float(persona.novelty_weight)*100:.0f}%): Originality and freshness of ideas
- **Structure** ({float(persona.structure_weight)*100:.0f}%): Organization and logical flow
- **Thoroughness** ({float(persona.thoroughness_weight)*100:.0f}%): Depth, evidence, and coverage
- **Clarity** ({float(persona.clarity_weight)*100:.0f}%): Writing quality and readability

{format_rubric_for_prompt()}

## Evaluation Guidelines

1. **Stay in character**: Apply your persona's values consistently. If you value evidence, penalize unsupported claims. If you value originality, reward intellectual risk-taking.

2. **Be calibrated**: A score of 7 represents good, professional-quality work. Scores of 9+ should be rare and reserved for exceptional work. Scores below 4 indicate significant problems.

3. **Provide actionable feedback**: Your feedback should reflect your persona's priorities and help authors understand your perspective.

4. **Consider the novelty context**: When provided, use information about similar existing works to inform your evaluation.

## Output Format

Respond with valid JSON in exactly this format:
{{
  "novelty": {{
    "score": <number 1-10, can use decimals like 7.5>,
    "feedback": "<2-3 sentences explaining the score from your persona's perspective>"
  }},
  "structure": {{
    "score": <number 1-10>,
    "feedback": "<2-3 sentences>"
  }},
  "thoroughness": {{
    "score": <number 1-10>,
    "feedback": "<2-3 sentences>"
  }},
  "clarity": {{
    "score": <number 1-10>,
    "feedback": "<2-3 sentences>"
  }},
  "overall_summary": "<1 paragraph overall assessment from your persona's perspective, highlighting what you as {persona.name} found notable>"
}}"""


def compute_persona_weighted_score(
    persona: EvaluatorPersona,
    novelty: float,
    structure: float,
    thoroughness: float,
    clarity: float,
) -> Decimal:
    """Compute weighted score using persona-specific weights."""
    weights = persona.get_weights()
    weighted = (
        Decimal(str(novelty)) * weights["novelty"]
        + Decimal(str(structure)) * weights["structure"]
        + Decimal(str(thoroughness)) * weights["thoroughness"]
        + Decimal(str(clarity)) * weights["clarity"]
    )
    return weighted.quantize(Decimal("0.01"))


class MultiLLMJudge:
    """
    Multi-evaluator LLM Judge.

    Runs evaluations across multiple provider/persona combinations
    and aggregates results.
    """

    def __init__(
        self,
        db: AsyncSession,
        providers: Optional[List[str]] = None,
        personas: Optional[List[str]] = None,
        novelty_detector: Optional[NoveltyDetector] = None,
        aggregation_method: AggregationMethod = AggregationMethod.MEDIAN,
    ):
        self.db = db
        self.novelty_detector = novelty_detector or NoveltyDetector(db)
        self.aggregation_method = aggregation_method
        self.max_content_chars = 150000

        # Configure providers
        if providers is None:
            # Use configured providers from settings, filtered by availability
            configured = settings.evaluation_providers.split(",")
            available = get_available_providers()
            self.provider_names = [p.strip() for p in configured if p.strip() in available]
        else:
            self.provider_names = providers

        if not self.provider_names:
            # Fallback to claude if nothing available
            self.provider_names = ["claude"]

        # Configure personas
        if personas is None:
            configured = settings.evaluation_personas.split(",")
            self.persona_ids = [p.strip() for p in configured if p.strip()]
        else:
            self.persona_ids = personas

        if not self.persona_ids:
            self.persona_ids = ["rigorist", "synthesizer"]

    async def evaluate_ebook(self, ebook: Ebook) -> Evaluation:
        """
        Run full multi-evaluator pipeline for an ebook.

        Steps:
        1. Update evaluation status
        2. Run novelty detection
        3. Run all provider/persona evaluations in parallel
        4. Aggregate results
        5. Store individual and aggregated evaluations
        6. Update ebook status

        Returns:
            The completed Evaluation record with aggregated scores
        """
        evaluation = await self._get_or_create_evaluation(ebook.id)

        try:
            evaluation.status = EvaluationStatus.IN_PROGRESS
            evaluation.started_at = datetime.utcnow()
            await self.db.commit()

            # Step 1: Novelty detection
            novelty_result = await self.novelty_detector.analyze(ebook)

            # Step 2: Build common prompt components
            novelty_context = build_novelty_context(
                corpus_size=novelty_result.corpus_size,
                most_similar_title=novelty_result.most_similar_title,
                max_similarity=novelty_result.max_similarity,
                overlapping_themes=novelty_result.overlapping_themes,
            )

            content = self._truncate_content(ebook.content_markdown)

            user_prompt = JUDGE_EVALUATION_PROMPT.format(
                title=ebook.title,
                category=ebook.category,
                word_count=ebook.word_count,
                novelty_context=novelty_context,
                content=content,
            )

            # Step 3: Run all evaluations in parallel
            evaluation_tasks = []
            for provider_name in self.provider_names:
                for persona_id in self.persona_ids:
                    task = self._run_single_evaluation(
                        evaluation_id=evaluation.id,
                        ebook_id=ebook.id,
                        provider_name=provider_name,
                        persona_id=persona_id,
                        user_prompt=user_prompt,
                    )
                    evaluation_tasks.append(task)

            individual_results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)

            # Step 4: Process results and store individual evaluations
            individual_scores: List[IndividualScore] = []
            individual_evals: List[IndividualEvaluation] = []

            for result in individual_results:
                if isinstance(result, Exception):
                    # Log but continue with other evaluations
                    print(f"Evaluation failed: {result}")
                    continue

                indiv_eval, indiv_score = result
                individual_evals.append(indiv_eval)
                individual_scores.append(indiv_score)

            # Add all individual evaluations to DB
            for indiv_eval in individual_evals:
                self.db.add(indiv_eval)

            # Step 5: Aggregate results
            if not individual_scores:
                raise MultiEvaluationError("All individual evaluations failed")

            aggregated = aggregate_scores(individual_scores, self.aggregation_method)

            # Step 6: Update main evaluation record
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.utcnow()

            evaluation.novelty_score = aggregated.novelty_score
            evaluation.structure_score = aggregated.structure_score
            evaluation.thoroughness_score = aggregated.thoroughness_score
            evaluation.clarity_score = aggregated.clarity_score
            evaluation.overall_score = aggregated.overall_score

            # Generate combined feedback from successful evaluations
            evaluation.novelty_feedback = self._combine_feedback(
                individual_evals, "novelty_feedback"
            )
            evaluation.structure_feedback = self._combine_feedback(
                individual_evals, "structure_feedback"
            )
            evaluation.thoroughness_feedback = self._combine_feedback(
                individual_evals, "thoroughness_feedback"
            )
            evaluation.clarity_feedback = self._combine_feedback(
                individual_evals, "clarity_feedback"
            )
            evaluation.overall_summary = generate_consensus_summary(
                individual_scores, aggregated
            )

            # Novelty detection results
            evaluation.novelty_comparison_count = novelty_result.corpus_size
            evaluation.most_similar_ebook_id = novelty_result.most_similar_id
            evaluation.max_similarity_score = (
                Decimal(str(novelty_result.max_similarity))
                if novelty_result.max_similarity
                else None
            )

            # Multi-evaluator metadata
            evaluation.evaluator_count = aggregated.evaluator_count
            evaluation.aggregation_method = self.aggregation_method.value
            evaluation.judge_model = f"multi:{','.join(self.provider_names)}"
            evaluation.judge_prompt_version = "v2.0-multi"
            evaluation.raw_llm_response = {
                "aggregation": {
                    "method": self.aggregation_method.value,
                    "successful_count": aggregated.successful_count,
                    "score_std_dev": aggregated.score_std_dev,
                    "max_disagreement": aggregated.max_disagreement,
                    "breakdown": aggregated.evaluator_breakdown,
                },
                "providers": self.provider_names,
                "personas": self.persona_ids,
            }

            # Step 7: Update ebook status
            if aggregated.overall_score >= MINIMUM_OVERALL_SCORE:
                ebook.status = EbookStatus.PUBLISHED
                ebook.published_at = datetime.utcnow()
            else:
                ebook.status = EbookStatus.REJECTED

            await self.db.commit()
            await self.db.refresh(evaluation)

            return evaluation

        except Exception as e:
            evaluation.status = EvaluationStatus.FAILED
            evaluation.error_message = str(e)
            evaluation.completed_at = datetime.utcnow()
            ebook.status = EbookStatus.REJECTED
            await self.db.commit()
            raise MultiEvaluationError(f"Multi-evaluation failed: {e}") from e

    async def _run_single_evaluation(
        self,
        evaluation_id: UUID,
        ebook_id: UUID,
        provider_name: str,
        persona_id: str,
        user_prompt: str,
    ) -> Tuple[IndividualEvaluation, IndividualScore]:
        """
        Run a single provider/persona evaluation.

        Returns both the DB record and the score object for aggregation.
        """
        start_time = time.time()
        persona = get_persona(persona_id)
        provider = get_provider(provider_name)
        system_prompt = build_persona_system_prompt(persona)

        indiv_eval = IndividualEvaluation(
            evaluation_id=evaluation_id,
            ebook_id=ebook_id,
            provider=provider_name,
            model=provider.model,
            persona_id=persona_id,
        )

        try:
            # Call LLM
            response_text = await provider.evaluate(system_prompt, user_prompt)
            duration_ms = int((time.time() - start_time) * 1000)

            # Parse response
            scores = provider.parse_evaluation_response(response_text)

            # Compute persona-weighted score
            weighted = compute_persona_weighted_score(
                persona,
                scores["novelty"]["score"],
                scores["structure"]["score"],
                scores["thoroughness"]["score"],
                scores["clarity"]["score"],
            )

            # Populate individual evaluation
            indiv_eval.novelty_score = Decimal(str(scores["novelty"]["score"]))
            indiv_eval.structure_score = Decimal(str(scores["structure"]["score"]))
            indiv_eval.thoroughness_score = Decimal(str(scores["thoroughness"]["score"]))
            indiv_eval.clarity_score = Decimal(str(scores["clarity"]["score"]))
            indiv_eval.weighted_score = weighted

            indiv_eval.novelty_feedback = scores["novelty"]["feedback"]
            indiv_eval.structure_feedback = scores["structure"]["feedback"]
            indiv_eval.thoroughness_feedback = scores["thoroughness"]["feedback"]
            indiv_eval.clarity_feedback = scores["clarity"]["feedback"]
            indiv_eval.overall_summary = scores.get("overall_summary", "")

            indiv_eval.raw_response = {"response": response_text}
            indiv_eval.success = True
            indiv_eval.duration_ms = duration_ms

            # Create score object for aggregation
            indiv_score = IndividualScore(
                provider=provider_name,
                persona_id=persona_id,
                novelty_score=indiv_eval.novelty_score,
                structure_score=indiv_eval.structure_score,
                thoroughness_score=indiv_eval.thoroughness_score,
                clarity_score=indiv_eval.clarity_score,
                weighted_score=indiv_eval.weighted_score,
                success=True,
            )

            return indiv_eval, indiv_score

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            indiv_eval.success = False
            indiv_eval.error_message = str(e)
            indiv_eval.duration_ms = duration_ms

            # Return failed score for tracking
            indiv_score = IndividualScore(
                provider=provider_name,
                persona_id=persona_id,
                novelty_score=Decimal("0"),
                structure_score=Decimal("0"),
                thoroughness_score=Decimal("0"),
                clarity_score=Decimal("0"),
                weighted_score=Decimal("0"),
                success=False,
            )

            return indiv_eval, indiv_score

    async def _get_or_create_evaluation(self, ebook_id: UUID) -> Evaluation:
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
        """Truncate content if too long, preserving structure."""
        if len(content) <= self.max_content_chars:
            return content

        intro_len = int(self.max_content_chars * 0.5)
        conclusion_len = int(self.max_content_chars * 0.2)
        middle_len = self.max_content_chars - intro_len - conclusion_len

        intro = content[:intro_len]
        conclusion = content[-conclusion_len:]

        middle_start = len(content) // 3
        middle = content[middle_start : middle_start + middle_len]

        return (
            f"{intro}\n\n"
            f"[... content truncated for evaluation ({len(content):,} chars total) ...]\n\n"
            f"{middle}\n\n"
            f"[... content truncated ...]\n\n"
            f"{conclusion}"
        )

    def _combine_feedback(
        self, individual_evals: List[IndividualEvaluation], field: str
    ) -> str:
        """Combine feedback from multiple evaluators into a summary."""
        feedback_items = []
        for eval in individual_evals:
            if eval.success and getattr(eval, field, None):
                feedback = getattr(eval, field)
                persona = get_persona(eval.persona_id)
                feedback_items.append(f"**{persona.name}** ({eval.provider}): {feedback}")

        if not feedback_items:
            return ""

        return "\n\n".join(feedback_items)
