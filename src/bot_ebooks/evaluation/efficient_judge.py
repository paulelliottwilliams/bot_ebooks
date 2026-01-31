"""Intellectual quality LLM Judge.

Evaluates ebooks for intellectual substance — the kind of writing that gets
discussed in The Atlantic, Marginal Revolution, or smart podcasts.
Uses full content (no truncation) with Haiku for cost efficiency.
"""

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

settings = get_settings()


# Intellectual quality evaluation prompt
# Optimizes for writing that smart, curious people would find genuinely interesting
SYSTEM_PROMPT = """You are a senior editor at a publication like The Atlantic, Aeon, or Works in Progress — venues that publish serious ideas accessibly.

Your readers are intellectually curious professionals: the kind who read Tyler Cowen, listen to EconTalk, and actually finish long-form articles. They want genuine insight, not clickbait or credential-padding.

Score 1-10 on these dimensions:

- IDEAS (40%): Does this offer a genuinely novel thesis, surprising insight, or fresh framing? Does it make you think differently about something? Score 7+ only if you learned something or saw a familiar topic in a new light. A 5 is "competent but I've heard this before." An 8+ changes how you think.

- RIGOR (30%): Is this intellectually honest? Does it engage with counterarguments rather than strawmanning? Are claims supported with evidence or reasoning? Score 7+ for work that would survive scrutiny from a thoughtful critic. Deduct points for obvious gaps, motivated reasoning, or hand-waving.

- CRAFT (30%): Is this well-written? Clear prose, logical structure, appropriate depth? Does it respect the reader's intelligence without being needlessly obscure? Score 7+ for writing you'd actually enjoy reading. A 5 is "gets the point across." An 8+ is genuinely good prose.

CALIBRATION:
- 4-5: Competent but forgettable. Blog-post tier.
- 6: Solid. Worth reading if you're interested in the topic.
- 7: Good. Would recommend to a curious friend.
- 8: Excellent. Would share widely. "You have to read this."
- 9+: Exceptional. Would be talked about for years.

Think like someone curating a reading list for smart, busy people with limited time.

Respond ONLY with JSON: {"i":score,"r":score,"c":score,"f":"One sentence: what makes this worth reading (or not)?"}"""


USER_PROMPT = """SUBMISSION FOR REVIEW

Title: {title}
Category: {category}
Length: {word_count:,} words

---
{content}
---

Would this be worth your readers' time? Score it."""


class EfficientJudge:
    """
    Intellectual quality LLM Judge.

    Key design decisions:
    1. FULL CONTENT - No truncation, because you can't evaluate an argument
       without reading all of it
    2. INTELLECTUAL FOCUS - Asks "would smart, curious people find this interesting?"
       Think Atlantic, Marginal Revolution, EconTalk audience.
    3. HARSH CALIBRATION - Most submissions should score 4-6, 7+ is genuinely good
    4. USES HAIKU - ~10x cheaper than Sonnet, handles up to 200k tokens

    Cost estimate for a 50k word book (~65k tokens):
    - Haiku: ~$0.065 input + ~$0.002 output = ~$0.07 per evaluation
    - Sonnet would be: ~$0.20 input + ~$0.015 output = ~$0.22 per evaluation
    """

    # Minimum score to publish (weighted average must meet this)
    # 8.0 = "Excellent. Would share widely. You have to read this."
    PUBLISH_THRESHOLD = Decimal("8.0")

    def __init__(
        self,
        db: AsyncSession,
        anthropic_client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
    ):
        self.db = db
        self.anthropic = anthropic_client or AsyncAnthropic(
            api_key=settings.effective_anthropic_key or settings.anthropic_api_key
        )
        # Haiku handles up to 200k context, plenty for any ebook
        self.model = model or "claude-haiku-4-5-20251001"
        self.prompt_version = "v5.0-intellectual"

    async def evaluate_ebook(self, ebook: Ebook) -> Evaluation:
        """
        Run market-focused evaluation on FULL content.

        No truncation - the model reads the entire book.
        """
        evaluation = await self._get_or_create_evaluation(ebook.id)

        try:
            evaluation.status = EvaluationStatus.IN_PROGRESS
            evaluation.started_at = datetime.utcnow()
            await self.db.commit()

            # Send FULL content - no truncation
            prompt = USER_PROMPT.format(
                title=ebook.title,
                category=ebook.category,
                word_count=ebook.word_count,
                content=ebook.content_markdown,
            )

            # Single API call with full content
            response = await self.anthropic.messages.create(
                model=self.model,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )

            response_text = response.content[0].text

            # Parse response
            scores = self._parse_response(response_text)

            # Compute weighted overall score
            # IDEAS: 40%, RIGOR: 30%, CRAFT: 30%
            overall = (
                Decimal(str(scores["ideas"])) * Decimal("0.40") +
                Decimal(str(scores["rigor"])) * Decimal("0.30") +
                Decimal(str(scores["craft"])) * Decimal("0.30")
            ).quantize(Decimal("0.01"))

            # Update evaluation record
            # Map dimensions to existing DB columns
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.utcnow()

            # Store in existing columns (repurposed):
            # novelty -> ideas, structure -> rigor, thoroughness -> craft
            evaluation.novelty_score = Decimal(str(scores["ideas"]))
            evaluation.structure_score = Decimal(str(scores["rigor"]))
            evaluation.thoroughness_score = Decimal(str(scores["craft"]))
            evaluation.clarity_score = Decimal(str(scores["craft"]))  # duplicate for compatibility
            evaluation.overall_score = overall

            evaluation.overall_summary = scores.get("feedback", "")
            evaluation.novelty_feedback = f"Ideas score: {scores['ideas']}/10"
            evaluation.structure_feedback = f"Rigor score: {scores['rigor']}/10"
            evaluation.thoroughness_feedback = f"Craft score: {scores['craft']}/10"
            evaluation.clarity_feedback = ""

            evaluation.judge_model = self.model
            evaluation.judge_prompt_version = self.prompt_version
            evaluation.evaluator_count = 1
            evaluation.raw_llm_response = {
                "response": response_text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "dimensions": {
                    "ideas": scores["ideas"],
                    "rigor": scores["rigor"],
                    "craft": scores["craft"],
                },
            }

            # Stricter publish threshold
            if overall >= self.PUBLISH_THRESHOLD:
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
            raise

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

    def _parse_response(self, response_text: str) -> dict:
        """Parse the JSON response."""
        # Extract JSON
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if not json_match:
            raise ValueError(f"No JSON found in response: {response_text[:200]}")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        return {
            "ideas": self._validate_score(data.get("i", data.get("ideas", 5))),
            "rigor": self._validate_score(data.get("r", data.get("rigor", 5))),
            "craft": self._validate_score(data.get("c", data.get("craft", 5))),
            "feedback": data.get("f", data.get("feedback", "")),
        }

    def _validate_score(self, score) -> float:
        """Validate and clamp score to 1-10 range."""
        try:
            s = float(score)
            return max(1.0, min(10.0, s))
        except (TypeError, ValueError):
            return 5.0
