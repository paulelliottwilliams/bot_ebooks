"""Main v1 API router combining all endpoints."""

from fastapi import APIRouter

from . import agents, ebooks, evaluation, leaderboard, transactions

router = APIRouter(prefix="/v1")

# Include all endpoint routers
router.include_router(agents.router)
router.include_router(ebooks.router)
router.include_router(transactions.router)
router.include_router(leaderboard.router)
router.include_router(evaluation.router)
