"""Gating mechanism for agent approval (stub for Phase 1)."""

from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent


class GatingStatus(str, Enum):
    """Possible gating statuses for an agent."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GatingService:
    """
    Service for managing agent gating/approval.

    Phase 1: Auto-approve all agents.
    Future: Implement actual gating logic (CAPTCHA, proof-of-work, vouching, etc.)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_gating(self, agent: Agent) -> GatingStatus:
        """Check if agent passes gating requirements."""
        # Phase 1: Auto-approve
        return GatingStatus.APPROVED

    async def request_approval(
        self,
        agent_id: UUID,
        metadata: Optional[dict] = None,
    ) -> GatingStatus:
        """
        Request gating approval for an agent.

        Phase 1: Instant approval.
        Future: Queue for review, require proof, etc.
        """
        return GatingStatus.APPROVED

    async def update_gating_status(
        self,
        agent_id: UUID,
        status: GatingStatus,
        reason: Optional[str] = None,
    ) -> None:
        """
        Admin function to update gating status.

        This would be used by moderators/admins in future phases.
        """
        agent = await self.db.get(Agent, agent_id)
        if agent:
            agent.gating_status = status.value
            if reason:
                agent.gating_metadata = reason
            await self.db.commit()
