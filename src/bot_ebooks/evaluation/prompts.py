"""Prompt templates for the LLM-Judge evaluation system."""

from .rubrics import format_rubric_for_prompt

JUDGE_SYSTEM_PROMPT = f"""You are an expert literary critic and academic reviewer evaluating non-fiction ebooks for the bot_ebooks marketplace. Your role is to provide fair, consistent, and constructive evaluations.

You will evaluate each ebook on four dimensions:
{format_rubric_for_prompt()}

## Evaluation Guidelines

1. **Be rigorous but fair**: A score of 7 represents good, professional-quality work. Scores of 9+ should be rare and reserved for exceptional work. Scores below 4 indicate significant problems.

2. **Consider context**: Adjust expectations based on the ebook's category. A philosophy ebook should be evaluated on strength of argumentation; a history ebook on accuracy and sourcing.

3. **Provide actionable feedback**: Your feedback should help authors understand what worked and what could be improved.

4. **Consider the novelty context**: When provided, use information about similar existing works to inform your novelty score. High similarity to existing works should lower the novelty score unless the ebook offers a genuinely different perspective.

## Output Format

Respond with valid JSON in exactly this format:
{{
  "novelty": {{
    "score": <number 1-10, can use decimals like 7.5>,
    "feedback": "<2-3 sentences explaining the score>"
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
  "overall_summary": "<1 paragraph overall assessment highlighting key strengths and areas for improvement>"
}}"""


JUDGE_EVALUATION_PROMPT = """Evaluate the following ebook:

**Title:** {title}
**Category:** {category}
**Word Count:** {word_count:,}

{novelty_context}

---
**CONTENT:**
---
{content}
---

Provide your evaluation as JSON following the format specified in your instructions."""


NOVELTY_CONTEXT_TEMPLATE = """**NOVELTY CONTEXT:**
This ebook has been compared against {corpus_size} existing ebooks in the corpus.
{similarity_info}
{theme_info}

Consider this context when evaluating novelty. High similarity to existing works should lower the novelty score unless the ebook offers a genuinely different perspective or argument."""


NOVELTY_CONTEXT_EMPTY = """**NOVELTY CONTEXT:**
This is among the first ebooks in the corpus. There are no existing works to compare against for novelty scoring. Evaluate novelty based on the originality of ideas relative to general knowledge."""


def build_novelty_context(
    corpus_size: int,
    most_similar_title: str | None = None,
    max_similarity: float | None = None,
    overlapping_themes: list[str] | None = None,
) -> str:
    """Build the novelty context section for the evaluation prompt."""
    if corpus_size == 0:
        return NOVELTY_CONTEXT_EMPTY

    similarity_info = ""
    if most_similar_title and max_similarity is not None:
        similarity_info = f'The most similar existing work is "{most_similar_title}" with a semantic similarity of {max_similarity:.1%}.'

    theme_info = ""
    if overlapping_themes:
        theme_info = f"Key overlapping themes with existing corpus: {', '.join(overlapping_themes)}"

    return NOVELTY_CONTEXT_TEMPLATE.format(
        corpus_size=corpus_size,
        similarity_info=similarity_info,
        theme_info=theme_info,
    )
