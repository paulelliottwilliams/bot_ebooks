"""Market-focused LLM Judge.

Evaluates ebooks like a publisher would: Will people pay money for this?
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


# Market-focused evaluation prompt
# Asks the question publishers actually care about: would someone BUY this?
MARKET_SYSTEM_PROMPT = """You are a acquisitions editor at a publishing house deciding whether to publish an ebook.

Your job is to predict: Would real readers PAY MONEY for this?

Score 1-10 on these dimensions:
- VALUE (40%): Does this solve a real problem or provide genuine insight readers would pay for? Is it better than free blog posts or Wikipedia? Score 7+ only if you'd recommend a friend buy it.
- QUALITY (30%): Is the writing professional? Are claims supported? Would readers feel satisfied or ripped off? Score 7+ only for work that meets professional publishing standards.
- MARKETABILITY (30%): Is there a clear audience who would want this? Does the title/premise attract interest? Score 7+ only if you can identify WHO would buy this and WHY.

BE HARSH. Most submissions should score 4-6. A 7 means "yes, publish this." An 8+ is genuinely good. A 9+ would be a bestseller.

Think like a businessperson spending money to publish this, not an academic grading a paper.

Respond ONLY with JSON: {"v":score,"q":score,"m":score,"f":"One sentence: would you publish this and why/why not?"}"""


MARKET_USER_PROMPT = """SUBMISSION FOR REVIEW

Title: {title}
Category: {category}
Length: {word_count:,} words

---
{content}
---

Would you publish this? Score it."""


class EfficientJudge:
    """
    Market-focused LLM Judge.

    Key design decisions:
    1. FULL CONTENT - No truncation, because you can't evaluate an argument
       without reading all of it
    2. MARKET FOCUS - Asks "would people pay for this?" not academic metrics
    3. HARSH CALIBRATION - Most books should score 4-6, not 7-8
    4. USES HAIKU - ~10x cheaper than Sonnet, handles up to 200k tokens

    Cost estimate for a 50k word book (~65k tokens):
    - Haiku: ~$0.065 input + ~$0.002 output = ~$0.07 per evaluation
    - Sonnet would be: ~$0.20 input + ~$0.015 output = ~$0.22 per evaluation
    """

    # Minimum score to publish (weighted average must meet this)
    PUBLISH_THRESHOLD = Decimal("6.0")  # Stricter than before

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
        self.model = model or "claude-haiku-4-5-20250115"
        self.prompt_version = "v4.0-market"

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
            prompt = MARKET_USER_PROMPT.format(
                title=ebook.title,
                category=ebook.category,
                word_count=ebook.word_count,
                content=ebook.content_markdown,
            )

            # Single API call with full content
            response = await self.anthropic.messages.create(
                model=self.model,
                system=MARKET_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )

            response_text = response.content[0].text

            # Parse response
            scores = self._parse_response(response_text)

            # Compute weighted overall score
            # VALUE: 40%, QUALITY: 30%, MARKETABILITY: 30%
            overall = (
                Decimal(str(scores["value"])) * Decimal("0.40") +
                Decimal(str(scores["quality"])) * Decimal("0.30") +
                Decimal(str(scores["marketability"])) * Decimal("0.30")
            ).quantize(Decimal("0.01"))

            # Update evaluation record
            # Map new dimensions to existing DB columns
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.utcnow()

            # Store in existing columns (repurposed):
            # novelty -> value, structure -> quality, thoroughness -> marketability
            evaluation.novelty_score = Decimal(str(scores["value"]))
            evaluation.structure_score = Decimal(str(scores["quality"]))
            evaluation.thoroughness_score = Decimal(str(scores["marketability"]))
            evaluation.clarity_score = Decimal(str(scores["marketability"]))  # duplicate for compatibility
            evaluation.overall_score = overall

            evaluation.overall_summary = scores.get("feedback", "")
            evaluation.novelty_feedback = f"Value score: {scores['value']}/10"
            evaluation.structure_feedback = f"Quality score: {scores['quality']}/10"
            evaluation.thoroughness_feedback = f"Marketability score: {scores['marketability']}/10"
            evaluation.clarity_feedback = ""

            evaluation.judge_model = self.model
            evaluation.judge_prompt_version = self.prompt_version
            evaluation.evaluator_count = 1
            evaluation.raw_llm_response = {
                "response": response_text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "dimensions": {
                    "value": scores["value"],
                    "quality": scores["quality"],
                    "marketability": scores["marketability"],
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
            "value": self._validate_score(data.get("v", data.get("value", 5))),
            "quality": self._validate_score(data.get("q", data.get("quality", 5))),
            "marketability": self._validate_score(data.get("m", data.get("marketability", 5))),
            "feedback": data.get("f", data.get("feedback", "")),
        }

    def _validate_score(self, score) -> float:
        """Validate and clamp score to 1-10 range."""
        try:
            s = float(score)
            return max(1.0, min(10.0, s))
        except (TypeError, ValueError):
            return 5.0
