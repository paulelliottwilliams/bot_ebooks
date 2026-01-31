"""Transaction schemas for API validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from ..models.transaction import TransactionType


class EbookBrief(BaseModel):
    """Brief ebook info for transaction records."""

    id: UUID
    title: str

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    """Transaction record response."""

    id: UUID
    transaction_type: TransactionType
    amount: Decimal
    buyer_balance_after: Optional[Decimal]
    seller_balance_after: Optional[Decimal]
    description: Optional[str]
    created_at: datetime
    ebook: Optional[EbookBrief]

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    items: List[TransactionResponse]
    total: int
    page: int
    pages: int


class PurchaseResponse(BaseModel):
    """Response after successful ebook purchase."""

    transaction_id: UUID
    ebook_id: UUID
    ebook_title: str
    amount: Decimal
    new_balance: Decimal
    content_url: str
    message: str = "Purchase successful"
