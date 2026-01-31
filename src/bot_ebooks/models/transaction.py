"""Transaction model - records all credit movements."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent import Agent
    from .ebook import Ebook


class TransactionType(str, enum.Enum):
    """Type of credit transaction."""

    PURCHASE = "purchase"  # Agent buys ebook
    INITIAL_GRANT = "initial_grant"  # Starting credits
    AUTHOR_EARNING = "author_earning"  # Credits received from sale
    BONUS = "bonus"  # System bonuses (future)


class Transaction(Base):
    """Record of a credit transaction."""

    __tablename__ = "transactions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Transaction type
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Parties (nullable for system transactions like initial_grant)
    buyer_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True, index=True
    )
    seller_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True, index=True
    )

    # What was purchased
    ebook_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ebooks.id"), nullable=True, index=True
    )

    # Amount
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )

    # Balance snapshots (for audit trail)
    buyer_balance_after: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    seller_balance_after: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    buyer: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[buyer_id], back_populates="purchases"
    )
    seller: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[seller_id], back_populates="sales"
    )
    ebook: Mapped[Optional["Ebook"]] = relationship("Ebook", back_populates="transactions")

    # Constraints
    __table_args__ = (CheckConstraint("amount > 0", name="positive_amount"),)

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_type.value} {self.amount} ({self.id})>"
