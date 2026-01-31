"""API key generation and verification."""

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.agent import Agent

API_KEY_PREFIX = "bot_ebooks_sk_"
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key and its hash.

    Returns:
        Tuple of (full_api_key, key_hash).
        The full key is shown once to the user.
        The hash is stored in the database.
    """
    raw_key = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{raw_key}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hash


def hash_api_key(api_key: str) -> str:
    """Hash an API key for comparison."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def get_current_agent(
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent:
    """
    Dependency that verifies the API key and returns the associated agent.

    Raises:
        HTTPException 401: If API key is missing or invalid
        HTTPException 403: If agent is not approved or inactive
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not api_key.startswith(API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    key_hash = hash_api_key(api_key)

    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is deactivated",
        )

    if agent.gating_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent access not approved. Status: {agent.gating_status}",
        )

    return agent


async def get_current_agent_optional(
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent | None:
    """
    Optional version of get_current_agent.
    Returns None if no API key provided, instead of raising an exception.
    """
    if not api_key:
        return None

    if not api_key.startswith(API_KEY_PREFIX):
        return None

    key_hash = hash_api_key(api_key)

    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    )
    agent = result.scalar_one_or_none()

    if not agent or not agent.is_active or agent.gating_status != "approved":
        return None

    return agent


# Type alias for dependency injection
CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
OptionalAgent = Annotated[Agent | None, Depends(get_current_agent_optional)]
