"""Credit service for managing the economy."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.agent import Agent
from ..models.ebook import Ebook
from ..models.transaction import Transaction, TransactionType

settings = get_settings()


class InsufficientCreditsError(Exception):
    """Raised when agent doesn't have enough credits."""

    def __init__(self, required: Decimal, balance: Decimal):
        self.required = required
        self.balance = balance
        super().__init__(f"Insufficient credits. Required: {required}, Balance: {balance}")


class AlreadyPurchasedError(Exception):
    """Raised when agent tries to purchase an already owned ebook."""

    pass


class CannotPurchaseOwnEbookError(Exception):
    """Raised when agent tries to purchase their own ebook."""

    pass


class EbookNotAvailableError(Exception):
    """Raised when ebook is not available for purchase."""

    pass


class CreditService:
    """Service for credit/economy operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_balance(self, agent_id: UUID) -> Decimal:
        """Get current credit balance for an agent."""
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return agent.credits_balance

    async def process_purchase(
        self,
        buyer_id: UUID,
        ebook_id: UUID,
    ) -> Transaction:
        """
        Process an ebook purchase, transferring credits from buyer to seller.

        Returns:
            The purchase transaction record.

        Raises:
            InsufficientCreditsError: If buyer doesn't have enough credits
            AlreadyPurchasedError: If buyer already owns the ebook
            CannotPurchaseOwnEbookError: If buyer is the author
            EbookNotAvailableError: If ebook is not published
        """
        # Get buyer with lock
        buyer = await self.db.get(Agent, buyer_id, with_for_update=True)
        if not buyer:
            raise ValueError(f"Buyer {buyer_id} not found")

        # Get ebook
        ebook = await self.db.get(Ebook, ebook_id)
        if not ebook:
            raise ValueError(f"Ebook {ebook_id} not found")

        # Check if ebook is published
        if not ebook.is_published:
            raise EbookNotAvailableError(f"Ebook {ebook_id} is not available for purchase")

        # Check if buyer is the author
        if buyer_id == ebook.author_id:
            raise CannotPurchaseOwnEbookError()

        # Check if already purchased
        existing = await self._check_existing_purchase(buyer_id, ebook_id)
        if existing:
            raise AlreadyPurchasedError()

        # Get seller with lock
        seller = await self.db.get(Agent, ebook.author_id, with_for_update=True)
        if not seller:
            raise ValueError(f"Seller {ebook.author_id} not found")

        price = ebook.credit_cost

        # Check buyer has sufficient credits
        if buyer.credits_balance < price:
            raise InsufficientCreditsError(required=price, balance=buyer.credits_balance)

        # Calculate author earning
        author_earning = price * settings.author_share

        # Update balances
        buyer.credits_balance -= price
        buyer.total_spent += price
        seller.credits_balance += author_earning
        seller.total_earned += author_earning

        # Update ebook metrics
        ebook.purchase_count += 1

        # Create purchase transaction
        purchase_tx = Transaction(
            transaction_type=TransactionType.PURCHASE,
            buyer_id=buyer_id,
            seller_id=seller.id,
            ebook_id=ebook_id,
            amount=price,
            buyer_balance_after=buyer.credits_balance,
            seller_balance_after=seller.credits_balance,
            description=f"Purchase of '{ebook.title}'",
        )
        self.db.add(purchase_tx)

        await self.db.commit()
        await self.db.refresh(purchase_tx)

        return purchase_tx

    async def _check_existing_purchase(
        self,
        buyer_id: UUID,
        ebook_id: UUID,
    ) -> bool:
        """Check if buyer has already purchased this ebook."""
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.buyer_id == buyer_id,
                Transaction.ebook_id == ebook_id,
                Transaction.transaction_type == TransactionType.PURCHASE,
            )
        )
        return result.scalar_one_or_none() is not None

    async def has_purchased(self, agent_id: UUID, ebook_id: UUID) -> bool:
        """Check if agent has purchased an ebook."""
        return await self._check_existing_purchase(agent_id, ebook_id)

    async def get_agent_purchases(
        self,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get all purchase transactions for an agent."""
        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.buyer_id == agent_id,
                Transaction.transaction_type == TransactionType.PURCHASE,
            )
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_agent_transactions(
        self,
        agent_id: UUID,
        transaction_type: Optional[TransactionType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get all transactions for an agent (as buyer or seller)."""
        query = select(Transaction).where(
            (Transaction.buyer_id == agent_id) | (Transaction.seller_id == agent_id)
        )

        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)

        result = await self.db.execute(
            query.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
