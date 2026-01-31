"""Token-efficient single-pass LLM Judge.

Optimized for minimal API usage while maintaining evaluation quality.
Uses a single API call with a compact prompt.
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
from .rubrics import MINIMUM_OVERALL_SCORE, compute_overall_score

settings = get_settings()


# Compact system prompt - much shorter than the original
EFFICIENT_SYSTEM_PROMPT = """You evaluate ebooks on 4 dimensions (1-10 scale):
- NOVELTY (30%): Originality of ideas. 7=fresh perspective, 9+=groundbreaking
- STRUCTURE (20%): Organization/flow. 7=well-organized, 9+=masterful
- THOROUGHNESS (30%): Depth/evidence. 7=comprehensive, 9+=exhaustive
- CLARITY (20%): Writing quality. 7=clear prose, 9+=exceptional

Respond ONLY with JSON: {"n":score,"s":score,"t":score,"c":score,"f":"one sentence overall"}"""


EFFICIENT_USER_PROMPT = """Title: {title}
Category: {category}
Words: {word_count}

{content}"""


class EfficientJudge:
    """
    Token-efficient LLM Judge.

    Optimizations:
    1. Single API call (not 10)
    2. Minimal system prompt (~100 tokens vs ~800)
    3. Compact JSON output format (~50 tokens vs ~500)
    4. Aggressive content truncation with smart sampling
    5. Uses Haiku for cost efficiency (or configurable)
    """

    def __init__(
        self,
        db: AsyncSession,
        anthropic_client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
        max_content_tokens: int = 8000,  # Much smaller default
    ):
        self.db = db
        self.anthropic = anthropic_client or AsyncAnthropic(
            api_key=settings.effective_anthropic_key or settings.anthropic_api_key
        )
        # Default to Haiku for efficiency - ~20x cheaper than Sonnet
        self.model = model or "claude-3-5-haiku-20241022"
        self.prompt_version = "v3.0-efficient"
        # ~4 chars per token, so 8000 tokens ≈ 32000 chars
        self.max_content_chars = max_content_tokens * 4

    async def evaluate_ebook(self, ebook: Ebook) -> Evaluation:
        """
        Run efficient single-pass evaluation.

        Token budget (approximate):
        - System prompt: ~100 tokens
        - User prompt overhead: ~50 tokens
        - Content: ~8000 tokens (configurable)
        - Output: ~100 tokens
        Total: ~8,250 tokens per evaluation

        Compare to multi-judge: ~380,000 tokens per evaluation
        That's ~46x more efficient!
        """
        evaluation = await self._get_or_create_evaluation(ebook.id)

        try:
            evaluation.status = EvaluationStatus.IN_PROGRESS
            evaluation.started_at = datetime.utcnow()
            await self.db.commit()

            # Build compact prompt
            content = self._smart_truncate(ebook.content_markdown)

            prompt = EFFICIENT_USER_PROMPT.format(
                title=ebook.title,
                category=ebook.category,
                word_count=ebook.word_count,
                content=content,
            )

            # Single API call
            response = await self.anthropic.messages.create(
                model=self.model,
                system=EFFICIENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,  # Compact output
            )

            response_text = response.content[0].text

            # Parse compact response
            scores = self._parse_compact_response(response_text)

            # Compute overall score
            overall = compute_overall_score({
                "novelty": scores["novelty"],
                "structure": scores["structure"],
                "thoroughness": scores["thoroughness"],
                "clarity": scores["clarity"],
            })

            # Update evaluation record
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.completed_at = datetime.utcnow()

            evaluation.novelty_score = Decimal(str(scores["novelty"]))
            evaluation.structure_score = Decimal(str(scores["structure"]))
            evaluation.thoroughness_score = Decimal(str(scores["thoroughness"]))
            evaluation.clarity_score = Decimal(str(scores["clarity"]))
            evaluation.overall_score = overall

            # Compact feedback
            evaluation.overall_summary = scores.get("feedback", "")
            evaluation.novelty_feedback = ""
            evaluation.structure_feedback = ""
            evaluation.thoroughness_feedback = ""
            evaluation.clarity_feedback = ""

            evaluation.judge_model = self.model
            evaluation.judge_prompt_version = self.prompt_version
            evaluation.evaluator_count = 1
            evaluation.raw_llm_response = {
                "response": response_text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            # Update ebook status
            if overall >= MINIMUM_OVERALL_SCORE:
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

    def _smart_truncate(self, content: str) -> str:
        """
        Smart truncation that preserves signal while minimizing tokens.

        Strategy:
        - Keep title/intro (first 20%)
        - Sample key sections from middle (40%)
        - Keep conclusion (20%)
        - Reserve 20% for section headers throughout
        """
        if len(content) <= self.max_content_chars:
            return content

        # Calculate budgets
        intro_budget = int(self.max_content_chars * 0.25)
        middle_budget = int(self.max_content_chars * 0.35)
        conclusion_budget = int(self.max_content_chars * 0.20)
        headers_budget = int(self.max_content_chars * 0.20)

        # Extract intro
        intro = content[:intro_budget]

        # Extract conclusion
        conclusion = content[-conclusion_budget:]

        # Extract section headers (lines starting with #)
        headers = []
        for line in content.split('\n'):
            if line.strip().startswith('#'):
                headers.append(line.strip())
        headers_text = '\n'.join(headers[:20])  # Max 20 headers
        if len(headers_text) > headers_budget:
            headers_text = headers_text[:headers_budget]

        # Sample from middle
        middle_start = len(content) // 3
        middle = content[middle_start:middle_start + middle_budget]

        truncation_note = f"\n[...truncated from {len(content):,} chars...]\n"

        return f"{intro}{truncation_note}STRUCTURE:\n{headers_text}{truncation_note}{middle}{truncation_note}{conclusion}"

    def _parse_compact_response(self, response_text: str) -> dict:
        """Parse the compact JSON response."""
        # Extract JSON
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if not json_match:
            raise ValueError(f"No JSON found in response: {response_text[:200]}")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Map compact keys to full names
        return {
            "novelty": self._validate_score(data.get("n", data.get("novelty", 5))),
            "structure": self._validate_score(data.get("s", data.get("structure", 5))),
            "thoroughness": self._validate_score(data.get("t", data.get("thoroughness", 5))),
            "clarity": self._validate_score(data.get("c", data.get("clarity", 5))),
            "feedback": data.get("f", data.get("feedback", "")),
        }

    def _validate_score(self, score) -> float:
        """Validate and clamp score to 1-10 range."""
        try:
            s = float(score)
            return max(1.0, min(10.0, s))
        except (TypeError, ValueError):
            return 5.0  # Default to middle score
