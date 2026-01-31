"""API dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..services.agent_service import AgentService
from ..services.credit_service import CreditService
from ..services.ebook_service import EbookService
from ..services.leaderboard_service import LeaderboardService

# Database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


# Service factory dependencies
def get_agent_service(db: DbSession) -> AgentService:
    return AgentService(db)


def get_ebook_service(db: DbSession) -> EbookService:
    return EbookService(db)


def get_credit_service(db: DbSession) -> CreditService:
    return CreditService(db)


def get_leaderboard_service(db: DbSession) -> LeaderboardService:
    return LeaderboardService(db)


# Service type aliases
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
EbookServiceDep = Annotated[EbookService, Depends(get_ebook_service)]
CreditServiceDep = Annotated[CreditService, Depends(get_credit_service)]
LeaderboardServiceDep = Annotated[LeaderboardService, Depends(get_leaderboard_service)]
