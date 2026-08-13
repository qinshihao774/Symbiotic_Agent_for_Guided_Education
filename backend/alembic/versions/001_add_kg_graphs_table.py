"""add kg_graphs table

Revision ID: 001
Revises:
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kg_graphs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("graph_name", sa.String(128), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(256), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("node_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("edge_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_kg_graphs_user_id", "kg_graphs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_kg_graphs_user_id", "kg_graphs")
    op.drop_table("kg_graphs")
