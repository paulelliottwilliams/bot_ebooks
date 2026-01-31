"""Tests for ebook API endpoints."""

import pytest
from httpx import AsyncClient


SAMPLE_EBOOK_CONTENT = """# The Rise and Fall of Ancient Rome

## Introduction

Rome's history spans over a thousand years, from its legendary founding in 753 BCE
to the fall of the Western Roman Empire in 476 CE. This ebook examines the key
factors that contributed to Rome's unprecedented rise and eventual decline.

## Chapter 1: The Roman Republic

The Roman Republic was established in 509 BCE after the overthrow of the last
Roman king, Lucius Tarquinius Superbus. This period saw Rome transform from a
small city-state into a Mediterranean superpower.

### The Senate and the People

The Roman political system was built on a delicate balance between the patrician
Senate and the plebeian assemblies. This system, while often contentious, provided
a framework for governance that would influence political thought for millennia.

## Chapter 2: Imperial Expansion

Under the Republic and later the Empire, Rome expanded to control the entire
Mediterranean basin, as well as much of Western Europe, North Africa, and the
Middle East. This expansion was driven by a combination of military prowess,
diplomatic skill, and cultural assimilation.

## Conclusion

The Roman experience offers valuable lessons about the nature of power, the
challenges of governance, and the factors that contribute to the rise and fall
of civilizations. Understanding Rome helps us better understand our own world.
"""


@pytest.mark.asyncio
async def test_submit_ebook(authenticated_client: AsyncClient):
    """Test ebook submission."""
    response = await authenticated_client.post(
        "/api/v1/ebooks",
        json={
            "title": "The Rise and Fall of Ancient Rome",
            "subtitle": "A Historical Analysis",
            "description": "An examination of Roman history",
            "category": "history",
            "tags": ["rome", "ancient-history", "empire"],
            "content_markdown": SAMPLE_EBOOK_CONTENT,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "The Rise and Fall of Ancient Rome"
    assert data["status"] == "pending_evaluation"
    assert "ebook_id" in data


@pytest.mark.asyncio
async def test_submit_ebook_invalid_category(authenticated_client: AsyncClient):
    """Test that invalid categories are rejected."""
    response = await authenticated_client.post(
        "/api/v1/ebooks",
        json={
            "title": "Test Ebook",
            "category": "invalid_category",
            "content_markdown": SAMPLE_EBOOK_CONTENT,
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_ebook_unauthorized(client: AsyncClient):
    """Test that unauthenticated submissions are rejected."""
    response = await client.post(
        "/api/v1/ebooks",
        json={
            "title": "Test Ebook",
            "category": "history",
            "content_markdown": SAMPLE_EBOOK_CONTENT,
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_ebooks(client: AsyncClient):
    """Test listing ebooks."""
    response = await client.get("/api/v1/ebooks")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_list_ebooks_with_filters(client: AsyncClient):
    """Test listing ebooks with filters."""
    response = await client.get(
        "/api/v1/ebooks",
        params={
            "category": "history",
            "sort_by": "created_at",
            "sort_order": "desc",
            "page": 1,
            "per_page": 10,
        },
    )

    assert response.status_code == 200
