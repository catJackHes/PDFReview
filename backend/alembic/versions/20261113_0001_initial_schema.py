"""Initial schema baseline for the PDF review MVP.

Revision ID: 20261113_0001
Revises: None
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261113_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_company_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_files",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("pdf_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("applies_to", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_key", "version", name="uq_rule_version_key_version"),
    )
    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engine_version", sa.String(120), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("review_run_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("file_id", sa.String(64), nullable=True),
        sa.Column("rule_version_id", sa.String(64), nullable=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("machine_result", sa.String(30), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("file_id", sa.String(64), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text_excerpt", sa.Text(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "annotations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("file_id", sa.String(64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("supersedes_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_actions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("finding_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=False),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "audit_events", "review_actions", "annotations", "evidence", "findings",
        "review_runs", "rule_versions", "project_files", "projects", "companies", "users",
    ):
        op.drop_table(table)
