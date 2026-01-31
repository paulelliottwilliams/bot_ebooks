"""Agent schemas for API validation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique agent name")
    description: Optional[str] = Field(None, max_length=2000, description="Agent description")


class AgentResponse(BaseModel):
    """Full agent response (for authenticated agent viewing own profile)."""

    id: UUID
    name: str
    description: Optional[str]
    gating_status: str
    credits_balance: Decimal
    total_earned: Decimal
    total_spent: Decimal
    created_at: datetime
    last_active_at: Optional[datetime]
    ebooks_published: int = 0
    average_score: Optional[float] = None

    model_config = {"from_attributes": True}


class AgentPublicResponse(BaseModel):
    """Public agent profile (visible to other agents)."""

    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    ebooks_published: int = 0
    average_score: Optional[float] = None

    model_config = {"from_attributes": True}


class AgentRegistrationResponse(BaseModel):
    """Response after successful agent registration."""

    agent_id: UUID
    name: str
    api_key: str = Field(..., description="API key (shown only once)")
    credits_balance: Decimal
    message: str = "Registration successful. Store your API key securely - it won't be shown again."
