"""add document_chunks table for pgvector RAG

Revision ID: 003
Revises: 002
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Enable pg_trgm for GIN trigram index on chapter_path
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("kg_graph_id", sa.BigInteger(), nullable=True),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add foreign key referencing kg_graphs
    op.create_foreign_key(
        "fk_document_chunks_kg_graph",
        "document_chunks", "kg_graphs",
        ["kg_graph_id"], ["id"],
        ondelete="SET NULL",
    )

    # Add pgvector column as raw SQL (SQLAlchemy has no native vector type)
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN embedding vector(1024)"
    )

    # Create HNSW index
    op.execute(
        "CREATE INDEX idx_doc_chunks_embedding "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )

    # Create auxiliary indexes
    op.execute(
        "CREATE INDEX idx_doc_chunks_course "
        "ON document_chunks (course_id)"
    )
    op.execute(
        "CREATE INDEX idx_doc_chunks_chapter "
        "ON document_chunks USING gin ((metadata->>'chapter_path') gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
