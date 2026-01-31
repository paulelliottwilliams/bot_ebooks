"""Agent service for business logic."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.api_keys import generate_api_key
from ..config import get_settings
from ..models.agent import Agent
from ..models.ebook import Ebook, EbookStatus
from ..models.evaluation import Evaluation
from ..models.transaction import Transaction, TransactionType
from ..schemas.agent import AgentCreate

settings = get_settings()


class AgentService:
    """Service for agent-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(self, data: AgentCreate) -> tuple[Agent, str]:
        """
        Create a new agent with initial credits.

        Returns:
            Tuple of (agent, api_key). The API key is only returned once.
        """
        # Generate API key
        api_key, key_hash = generate_api_key()

        # Create agent
        agent = Agent(
            name=data.name,
            description=data.description,
            api_key_hash=key_hash,
            gating_status="approved",  # Auto-approve for Phase 1
            credits_balance=settings.initial_credits,
        )
        self.db.add(agent)
        await self.db.flush()

        # Create initial grant transaction
        transaction = Transaction(
            transaction_type=TransactionType.INITIAL_GRANT,
            buyer_id=agent.id,
            amount=settings.initial_credits,
            buyer_balance_after=agent.credits_balance,
            description="Initial credit grant for new agent",
        )
        self.db.add(transaction)

        await self.db.commit()
        await self.db.refresh(agent)

        return agent, api_key

    async def get_agent_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent by ID."""
        return await self.db.get(Agent, agent_id)

    async def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get agent by name."""
        result = await self.db.execute(
            select(Agent).where(Agent.name == name)
        )
        return result.scalar_one_or_none()

    async def update_last_active(self, agent: Agent) -> None:
        """Update agent's last active timestamp."""
        agent.last_active_at = datetime.utcnow()
        await self.db.commit()

    async def get_agent_stats(self, agent_id: UUID) -> dict:
        """Get agent statistics including ebook count and average score."""
        # Count published ebooks
        ebook_count_result = await self.db.execute(
            select(func.count(Ebook.id)).where(
                Ebook.author_id == agent_id,
                Ebook.status == EbookStatus.PUBLISHED,
            )
        )
        ebook_count = ebook_count_result.scalar() or 0

        # Calculate average score
        avg_score_result = await self.db.execute(
            select(func.avg(Evaluation.overall_score))
            .join(Ebook, Evaluation.ebook_id == Ebook.id)
            .where(
                Ebook.author_id == agent_id,
                Ebook.status == EbookStatus.PUBLISHED,
            )
        )
        avg_score = avg_score_result.scalar()

        return {
            "ebooks_published": ebook_count,
            "average_score": float(avg_score) if avg_score else None,
        }

    async def name_exists(self, name: str) -> bool:
        """Check if agent name already exists."""
        result = await self.db.execute(
            select(func.count(Agent.id)).where(Agent.name == name)
        )
        return (result.scalar() or 0) > 0
