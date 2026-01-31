"""Ebook schemas for API validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.ebook import EbookStatus


# Valid categories for non-fiction ebooks
VALID_CATEGORIES = [
    "history",
    "philosophy",
    "political_science",
    "economics",
    "sociology",
    "psychology",
    "science",
    "technology",
    "current_events",
    "biography",
    "essays",
    "other",
]


class EbookCreate(BaseModel):
    """Schema for creating/submitting a new ebook."""

    title: str = Field(..., min_length=1, max_length=500)
    subtitle: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    category: str = Field(..., description="Category of the ebook")
    tags: List[str] = Field(default_factory=list, max_length=10)
    content_markdown: str = Field(..., min_length=100, description="Full ebook content in markdown")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        v_lower = v.lower().replace(" ", "_")
        if v_lower not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}")
        return v_lower

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        # Normalize and deduplicate tags
        return list(set(tag.lower().strip()[:50] for tag in v if tag.strip()))


class AuthorSummary(BaseModel):
    """Brief author info for ebook listings."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class EvaluationSummary(BaseModel):
    """Brief evaluation info for ebook listings."""

    overall_score: Optional[Decimal]
    novelty_score: Optional[Decimal]
    structure_score: Optional[Decimal]
    thoroughness_score: Optional[Decimal]
    clarity_score: Optional[Decimal]

    model_config = {"from_attributes": True}


class EbookResponse(BaseModel):
    """Basic ebook info for list views."""

    id: UUID
    title: str
    subtitle: Optional[str]
    category: str
    tags: List[str]
    word_count: int
    status: EbookStatus
    credit_cost: Decimal
    purchase_count: int
    created_at: datetime
    published_at: Optional[datetime]
    author: AuthorSummary
    overall_score: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class EbookListResponse(BaseModel):
    """Paginated list of ebooks."""

    items: List[EbookResponse]
    total: int
    page: int
    pages: int
    per_page: int


class EbookDetailResponse(BaseModel):
    """Detailed ebook info (without content)."""

    id: UUID
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    category: str
    tags: List[str]
    word_count: int
    status: EbookStatus
    credit_cost: Decimal
    purchase_count: int
    view_count: int
    created_at: datetime
    published_at: Optional[datetime]
    author: AuthorSummary
    evaluation: Optional[EvaluationSummary]
    is_purchased: bool = False
    is_author: bool = False

    model_config = {"from_attributes": True}


class EbookContentResponse(BaseModel):
    """Full ebook content (only accessible after purchase or by author)."""

    id: UUID
    title: str
    content_markdown: str

    model_config = {"from_attributes": True}


class EbookSubmissionResponse(BaseModel):
    """Response after submitting an ebook."""

    ebook_id: UUID
    title: str
    status: EbookStatus
    message: str = "Ebook submitted successfully. Evaluation will begin shortly."
