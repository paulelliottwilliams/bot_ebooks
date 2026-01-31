"""Multi-provider LLM support for evaluation.

Supports Claude (Anthropic), GPT (OpenAI), and Gemini (Google).
Each provider implements a common interface for evaluation calls.
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..config import get_settings

settings = get_settings()


@dataclass
class EvaluationResult:
    """Raw result from a single LLM evaluation call."""

    provider: str
    model: str
    novelty_score: float
    structure_score: float
    thoroughness_score: float
    clarity_score: float
    novelty_feedback: str
    structure_feedback: str
    thoroughness_feedback: str
    clarity_feedback: str
    overall_summary: str
    raw_response: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_name: str

    @abstractmethod
    async def evaluate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Make an evaluation call and return the raw response text."""
        pass

    def parse_evaluation_response(self, response_text: str) -> dict:
        """Parse the JSON evaluation response from the LLM."""
        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            raise ValueError("No JSON found in LLM response")

        json_str = json_match.group()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {e}")

        # Validate required fields
        required_dims = ["novelty", "structure", "thoroughness", "clarity"]
        for dim in required_dims:
            if dim not in data:
                raise ValueError(f"Missing dimension in response: {dim}")
            if "score" not in data[dim]:
                raise ValueError(f"Missing score for dimension: {dim}")
            if "feedback" not in data[dim]:
                data[dim]["feedback"] = ""

            # Validate score range
            score = float(data[dim]["score"])
            if not 1 <= score <= 10:
                raise ValueError(f"Score for {dim} out of range: {score}")

        return data


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider."""

    provider_name = "claude"

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=settings.effective_anthropic_key)
        return self._client

    async def evaluate(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2000,
        )
        return response.content[0].text


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    provider_name = "openai"

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.effective_openai_key)
        return self._client

    async def evaluate(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
        )
        return response.choices[0].message.content


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    provider_name = "gemini"

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.effective_google_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    async def evaluate(self, system_prompt: str, user_prompt: str) -> str:
        # Gemini combines system and user prompts differently
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        # Gemini's async API
        response = await self.client.generate_content_async(full_prompt)
        return response.text


# Provider registry
PROVIDERS = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}

# Default models for each provider
DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-pro",
}


def get_provider(provider_name: str, model: Optional[str] = None) -> LLMProvider:
    """Get an LLM provider instance."""
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")

    model = model or DEFAULT_MODELS.get(provider_name)
    return PROVIDERS[provider_name](model=model)


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    available = []

    if settings.effective_anthropic_key:
        available.append("claude")
    if settings.effective_openai_key:
        available.append("openai")
    if settings.effective_google_key:
        available.append("gemini")

    return available


def get_default_providers() -> list[LLMProvider]:
    """Get instances of all available providers with default models."""
    return [get_provider(name) for name in get_available_providers()]
