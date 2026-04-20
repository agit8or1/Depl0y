"""AI Reports subsystem — create tables

Revision ID: 20260420_ai_reports
Revises:
Create Date: 2026-04-20

NOTE: This project does not currently use Alembic as its runtime migrator;
instead `app.core.database.init_db()` calls `Base.metadata.create_all()` which
creates any new tables whose models are imported at startup. The AI Reports
models are imported via `app.models` so they will be created automatically on
backend start. This file is kept for change-history purposes in case Alembic
is activated later.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260420_ai_reports"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_provider_settings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("provider", sa.String(length=50), unique=True, nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "power_cost_settings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("electricity_rate_per_kwh", sa.Float(), nullable=False, server_default="0.12"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "node_power_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("proxmox_nodes.id"), nullable=True),
        sa.Column("idle_watts", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("load_watts", sa.Integer(), nullable=False, server_default="350"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("node_id", name="uq_node_power_profile"),
    )

    op.create_table(
        "ai_report_runs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False, index=True),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="global"),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp(), index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("token_usage_json", sa.Text(), nullable=True),
        sa.Column("findings_json", sa.Text(), nullable=True),
        sa.Column("ai_narrative_json", sa.Text(), nullable=True),
        sa.Column("rendered_markdown", sa.Text(), nullable=True),
        sa.Column("rendered_html", sa.Text(), nullable=True),
        sa.Column("assumptions_json", sa.Text(), nullable=True),
        sa.Column("data_freshness_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("manual_notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "ai_report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="global"),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column("cadence", sa.String(length=20), nullable=False, server_default="weekly"),
        sa.Column("cron_expr", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("include_executive_summary", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("include_raw_appendix", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "node_metric_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("proxmox_nodes.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("cpu_pct", sa.Float(), nullable=True),
        sa.Column("memory_pct", sa.Float(), nullable=True),
        sa.Column("disk_pct", sa.Float(), nullable=True),
        sa.Column("vm_count", sa.Integer(), nullable=True),
        sa.Column("lxc_count", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_node_metric_snapshots_node_captured",
        "node_metric_snapshots",
        ["node_id", "captured_at"],
    )


def downgrade():
    op.drop_index("ix_node_metric_snapshots_node_captured", table_name="node_metric_snapshots")
    op.drop_table("node_metric_snapshots")
    op.drop_table("ai_report_schedules")
    op.drop_table("ai_report_runs")
    op.drop_table("node_power_profiles")
    op.drop_table("power_cost_settings")
    op.drop_table("ai_provider_settings")
