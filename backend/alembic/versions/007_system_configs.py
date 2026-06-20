"""Migration: system_configs table (Story 4.4)."""

revision = "007_system_configs"
down_revision = "006_pending_user_key"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(64), nullable=False),
        sa.Column("config_value", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("config_key", name="uq_system_configs_key"),
    )


def downgrade():
    op.drop_table("system_configs")
