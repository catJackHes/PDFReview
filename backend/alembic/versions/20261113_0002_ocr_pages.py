"""Persist page-level PDF/OCR extraction results.

Revision ID: 20261113_0002
Revises: 20261113_0001
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261113_0002"
down_revision = "20261113_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_pages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width_pt", sa.Float(), nullable=False),
        sa.Column("height_pt", sa.Float(), nullable=False),
        sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("native_text_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text_quality", sa.String(length=24), nullable=False, server_default="unknown"),
        sa.Column("ocr_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("parser_version", sa.String(length=64), nullable=False, server_default="pymupdf"),
        sa.Column("ocr_version", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["project_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "page_number", name="uq_file_page_number"),
    )
    op.create_index("ix_file_pages_file_id", "file_pages", ["file_id"])
    op.create_table(
        "text_blocks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("file_page_id", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_page_id"], ["file_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text_blocks_file_page_id", "text_blocks", ["file_page_id"])


def downgrade() -> None:
    op.drop_index("ix_text_blocks_file_page_id", table_name="text_blocks")
    op.drop_table("text_blocks")
    op.drop_index("ix_file_pages_file_id", table_name="file_pages")
    op.drop_table("file_pages")
