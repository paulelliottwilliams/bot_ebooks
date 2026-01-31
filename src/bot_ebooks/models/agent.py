"""Agent model - represents an AI agent in the marketplace."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .ebook import Ebook
    from .transaction import Transaction


class Agent(Base):
    """An AI agent that can publish and purchase ebooks."""

    __tablename__ = "agents"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Identification
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Authentication
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Gating (stub for future implementation)
    gating_status: Mapped[str] = mapped_column(
        String(50), default="approved", nullable=False  # Auto-approve for Phase 1
    )
    gating_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Economy
    credits_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), default=Decimal("0.00"), nullable=False
    )
    total_earned: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), default=Decimal("0.00"), nullable=False
    )
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), default=Decimal("0.00"), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    ebooks: Mapped[List["Ebook"]] = relationship(
        "Ebook", back_populates="author", lazy="dynamic"
    )
    purchases: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.buyer_id",
        back_populates="buyer",
        lazy="dynamic",
    )
    sales: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.seller_id",
        back_populates="seller",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.id})>"
