"""Tests for agent API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient):
    """Test agent registration."""
    response = await client.post(
        "/api/v1/agents/register",
        json={"name": "TestBot", "description": "A test bot"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "TestBot"
    assert "api_key" in data
    assert data["api_key"].startswith("bot_ebooks_sk_")
    assert float(data["credits_balance"]) == 100.0


@pytest.mark.asyncio
async def test_register_duplicate_name(client: AsyncClient):
    """Test that duplicate names are rejected."""
    # First registration
    await client.post(
        "/api/v1/agents/register",
        json={"name": "DuplicateBot"},
    )

    # Second registration with same name
    response = await client.post(
        "/api/v1/agents/register",
        json={"name": "DuplicateBot"},
    )

    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_agent(authenticated_client: AsyncClient, test_agent):
    """Test getting own profile."""
    agent, _ = test_agent

    response = await authenticated_client.get("/api/v1/agents/me")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent.name
    assert float(data["credits_balance"]) == 100.0


@pytest.mark.asyncio
async def test_get_current_agent_unauthorized(client: AsyncClient):
    """Test that unauthenticated requests are rejected."""
    response = await client.get("/api/v1/agents/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_public_profile(authenticated_client: AsyncClient, test_agent):
    """Test getting a public agent profile."""
    agent, _ = test_agent

    response = await authenticated_client.get(f"/api/v1/agents/{agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent.name
    # Public profile should not include balance
    assert "credits_balance" not in data
