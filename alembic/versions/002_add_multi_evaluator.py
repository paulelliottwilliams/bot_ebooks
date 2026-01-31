"""Add multi-evaluator support.

Revision ID: 002
Revises: 001
Create Date: 2024-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to evaluations table
    op.add_column(
        "evaluations",
        sa.Column("evaluator_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "evaluations",
        sa.Column("aggregation_method", sa.String(50), nullable=True)
    )

    # Create individual_evaluations table
    op.create_table(
        "individual_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("persona_id", sa.String(50), nullable=False),
        sa.Column("novelty_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("structure_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("thoroughness_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("clarity_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("weighted_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("novelty_feedback", sa.Text(), nullable=True),
        sa.Column("structure_feedback", sa.Text(), nullable=True),
        sa.Column("thoroughness_feedback", sa.Text(), nullable=True),
        sa.Column("clarity_feedback", sa.Text(), nullable=True),
        sa.Column("overall_summary", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, default=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"]),
        sa.ForeignKeyConstraint(["ebook_id"], ["ebooks.id"]),
    )

    # Create indexes
    op.create_index(
        "ix_indiv_eval_evaluation_id",
        "individual_evaluations",
        ["evaluation_id"]
    )
    op.create_index(
        "ix_indiv_eval_ebook_id",
        "individual_evaluations",
        ["ebook_id"]
    )
    op.create_index(
        "ix_indiv_eval_provider_persona",
        "individual_evaluations",
        ["provider", "persona_id"]
    )
    op.create_index(
        "ix_indiv_eval_ebook_provider",
        "individual_evaluations",
        ["ebook_id", "provider"]
    )


def downgrade() -> None:
    op.drop_table("individual_evaluations")
    op.drop_column("evaluations", "aggregation_method")
    op.drop_column("evaluations", "evaluator_count")
