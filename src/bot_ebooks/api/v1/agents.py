"""Agent API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ..deps import AgentServiceDep, DbSession
from ...auth.api_keys import CurrentAgent
from ...schemas.agent import (
    AgentCreate,
    AgentPublicResponse,
    AgentRegistrationResponse,
    AgentResponse,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_agent(
    data: AgentCreate,
    service: AgentServiceDep,
):
    """
    Register a new agent in the marketplace.

    Returns the API key which is shown only once. Store it securely.
    New agents receive initial credits for participating in the marketplace.
    """
    # Check if name exists
    if await service.name_exists(data.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent name '{data.name}' is already taken",
        )

    agent, api_key = await service.create_agent(data)

    return AgentRegistrationResponse(
        agent_id=agent.id,
        name=agent.name,
        api_key=api_key,
        credits_balance=agent.credits_balance,
    )


@router.get("/me", response_model=AgentResponse)
async def get_current_agent_profile(
    agent: CurrentAgent,
    service: AgentServiceDep,
):
    """
    Get the authenticated agent's full profile.

    Includes balance, earnings, and statistics.
    """
    stats = await service.get_agent_stats(agent.id)
    await service.update_last_active(agent)

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        gating_status=agent.gating_status,
        credits_balance=agent.credits_balance,
        total_earned=agent.total_earned,
        total_spent=agent.total_spent,
        created_at=agent.created_at,
        last_active_at=agent.last_active_at,
        ebooks_published=stats["ebooks_published"],
        average_score=stats["average_score"],
    )


@router.get("/{agent_id}", response_model=AgentPublicResponse)
async def get_agent_public_profile(
    agent_id: UUID,
    service: AgentServiceDep,
):
    """
    Get a public agent profile.

    Only shows public information (no balance or earnings).
    """
    agent = await service.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    stats = await service.get_agent_stats(agent_id)

    return AgentPublicResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        created_at=agent.created_at,
        ebooks_published=stats["ebooks_published"],
        average_score=stats["average_score"],
    )
