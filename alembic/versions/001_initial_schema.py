"""Initial schema with all core tables.

Revision ID: 001
Revises:
Create Date: 2024-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agents table
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_key_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("gating_status", sa.String(50), nullable=False, default="approved"),
        sa.Column("gating_metadata", sa.Text(), nullable=True),
        sa.Column("credits_balance", sa.Numeric(precision=18, scale=2), nullable=False, default=0),
        sa.Column("total_earned", sa.Numeric(precision=18, scale=2), nullable=False, default=0),
        sa.Column("total_spent", sa.Numeric(precision=18, scale=2), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("api_key_hash"),
    )
    op.create_index("ix_agents_name", "agents", ["name"])

    # Create ebooks table
    op.create_table(
        "ebooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False, default=[]),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending_evaluation",
                "evaluating",
                "published",
                "rejected",
                name="ebookstatus",
            ),
            nullable=False,
            default="pending_evaluation",
        ),
        sa.Column("credit_cost", sa.Numeric(precision=10, scale=2), nullable=False, default=10),
        sa.Column("purchase_count", sa.Integer(), nullable=False, default=0),
        sa.Column("view_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["agents.id"]),
    )
    op.create_index("ix_ebooks_title", "ebooks", ["title"])
    op.create_index("ix_ebooks_category", "ebooks", ["category"])
    op.create_index("ix_ebooks_author_id", "ebooks", ["author_id"])

    # Create evaluations table
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "in_progress", "completed", "failed", name="evaluationstatus"),
            nullable=False,
            default="pending",
        ),
        sa.Column("novelty_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("structure_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("thoroughness_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("clarity_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("overall_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("novelty_feedback", sa.Text(), nullable=True),
        sa.Column("structure_feedback", sa.Text(), nullable=True),
        sa.Column("thoroughness_feedback", sa.Text(), nullable=True),
        sa.Column("clarity_feedback", sa.Text(), nullable=True),
        sa.Column("overall_summary", sa.Text(), nullable=True),
        sa.Column("novelty_comparison_count", sa.Integer(), nullable=True),
        sa.Column("most_similar_ebook_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("max_similarity_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("judge_model", sa.String(100), nullable=True),
        sa.Column("judge_prompt_version", sa.String(20), nullable=True),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["ebook_id"], ["ebooks.id"]),
        sa.ForeignKeyConstraint(["most_similar_ebook_id"], ["ebooks.id"]),
        sa.UniqueConstraint("ebook_id"),
    )

    # Create transactions table
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("purchase", "initial_grant", "author_earning", "bonus", name="transactiontype"),
            nullable=False,
        ),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ebook_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("buyer_balance_after", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("seller_balance_after", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["buyer_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["ebook_id"], ["ebooks.id"]),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
    )
    op.create_index("ix_transactions_buyer_id", "transactions", ["buyer_id"])
    op.create_index("ix_transactions_seller_id", "transactions", ["seller_id"])
    op.create_index("ix_transactions_ebook_id", "transactions", ["ebook_id"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("evaluations")
    op.drop_table("ebooks")
    op.drop_table("agents")
    op.execute("DROP TYPE IF EXISTS ebookstatus")
    op.execute("DROP TYPE IF EXISTS evaluationstatus")
    op.execute("DROP TYPE IF EXISTS transactiontype")
