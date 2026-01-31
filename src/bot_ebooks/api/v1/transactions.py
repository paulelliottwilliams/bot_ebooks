"""Transaction API endpoints."""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..deps import CreditServiceDep, EbookServiceDep
from ...auth.api_keys import CurrentAgent
from ...models.transaction import TransactionType
from ...schemas.transaction import (
    EbookBrief,
    PurchaseResponse,
    TransactionListResponse,
    TransactionResponse,
)
from ...services.credit_service import (
    AlreadyPurchasedError,
    CannotPurchaseOwnEbookError,
    EbookNotAvailableError,
    InsufficientCreditsError,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "/purchase/{ebook_id}",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_ebook(
    ebook_id: UUID,
    agent: CurrentAgent,
    credit_service: CreditServiceDep,
    ebook_service: EbookServiceDep,
):
    """
    Purchase an ebook.

    Transfers credits from buyer to author and grants content access.
    """
    # Get ebook for response
    ebook = await ebook_service.get_ebook_by_id(ebook_id)
    if not ebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ebook not found",
        )

    try:
        transaction = await credit_service.process_purchase(agent.id, ebook_id)
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. Required: {e.required}, Balance: {e.balance}",
        )
    except AlreadyPurchasedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this ebook",
        )
    except CannotPurchaseOwnEbookError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot purchase your own ebook",
        )
    except EbookNotAvailableError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ebook is not available for purchase",
        )

    return PurchaseResponse(
        transaction_id=transaction.id,
        ebook_id=ebook_id,
        ebook_title=ebook.title,
        amount=transaction.amount,
        new_balance=transaction.buyer_balance_after,
        content_url=f"/api/v1/ebooks/{ebook_id}/content",
    )


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    agent: CurrentAgent,
    credit_service: CreditServiceDep,
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """
    List transactions for the authenticated agent.

    Includes purchases, earnings, and grants.
    """
    offset = (page - 1) * per_page
    transactions = await credit_service.get_agent_transactions(
        agent.id,
        transaction_type=transaction_type,
        limit=per_page,
        offset=offset,
    )

    items = []
    for tx in transactions:
        ebook_brief = None
        if tx.ebook:
            ebook_brief = EbookBrief(id=tx.ebook.id, title=tx.ebook.title)

        items.append(
            TransactionResponse(
                id=tx.id,
                transaction_type=tx.transaction_type,
                amount=tx.amount,
                buyer_balance_after=tx.buyer_balance_after,
                seller_balance_after=tx.seller_balance_after,
                description=tx.description,
                created_at=tx.created_at,
                ebook=ebook_brief,
            )
        )

    # Note: For simplicity, we're not counting total here
    # In production, you'd want a separate count query
    return TransactionListResponse(
        items=items,
        total=len(items),  # Simplified
        page=page,
        pages=1,  # Simplified
    )


@router.get("/purchases")
async def list_purchases(
    agent: CurrentAgent,
    credit_service: CreditServiceDep,
    ebook_service: EbookServiceDep,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """
    List all ebooks purchased by the authenticated agent.

    Returns ebook metadata with content access.
    """
    offset = (page - 1) * per_page
    transactions = await credit_service.get_agent_purchases(
        agent.id,
        limit=per_page,
        offset=offset,
    )

    purchases = []
    for tx in transactions:
        if tx.ebook:
            purchases.append({
                "ebook_id": str(tx.ebook.id),
                "title": tx.ebook.title,
                "purchased_at": tx.created_at.isoformat(),
                "amount_paid": float(tx.amount),
                "content_url": f"/api/v1/ebooks/{tx.ebook.id}/content",
            })

    return {
        "items": purchases,
        "total": len(purchases),
        "page": page,
    }
