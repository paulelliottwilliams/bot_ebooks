"""Pytest fixtures for testing."""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.bot_ebooks.main import app
from src.bot_ebooks.models import Base
from src.bot_ebooks.db.session import get_db
from src.bot_ebooks.auth.api_keys import generate_api_key
from src.bot_ebooks.models.agent import Agent
from src.bot_ebooks.config import get_settings

settings = get_settings()

# Use a separate test database
TEST_DATABASE_URL = settings.database_url.replace("/bot_ebooks", "/bot_ebooks_test")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_agent(db_session: AsyncSession) -> tuple[Agent, str]:
    """Create a test agent and return (agent, api_key)."""
    api_key, key_hash = generate_api_key()

    agent = Agent(
        id=uuid4(),
        name=f"TestAgent_{uuid4().hex[:8]}",
        description="Test agent for automated testing",
        api_key_hash=key_hash,
        gating_status="approved",
        credits_balance=100,
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)

    return agent, api_key


@pytest_asyncio.fixture
async def authenticated_client(
    client: AsyncClient, test_agent: tuple[Agent, str]
) -> AsyncClient:
    """Create authenticated test client."""
    _, api_key = test_agent
    client.headers["X-API-Key"] = api_key
    return client
