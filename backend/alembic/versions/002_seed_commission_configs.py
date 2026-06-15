"""seed commission configs

Revision ID: 002
Revises: 001
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    commission_configs = sa.table(
        'commission_configs',
        sa.column('role', sa.Enum('agent', 'distributor', 'user')),
        sa.column('scene', sa.String(32)),
        sa.column('reward_type', sa.Enum('fixed', 'percentage')),
        sa.column('reward_value', sa.DECIMAL(10, 4)),
    )

    op.bulk_insert(
        commission_configs,
        [
            {'role': 'agent', 'scene': 'self_sell', 'reward_type': 'fixed', 'reward_value': 488.40},
            {'role': 'agent', 'scene': 'recruit_agent', 'reward_type': 'fixed', 'reward_value': 5500.00},
            {'role': 'agent', 'scene': 'recruit_distributor', 'reward_type': 'fixed', 'reward_value': 2750.00},
            {'role': 'agent', 'scene': 'downline_sell', 'reward_type': 'fixed', 'reward_value': 133.20},
            {'role': 'agent', 'scene': 'team_bonus', 'reward_type': 'percentage', 'reward_value': 0.05},
            {'role': 'distributor', 'scene': 'self_sell', 'reward_type': 'fixed', 'reward_value': 355.20},
            {'role': 'distributor', 'scene': 'recruit_agent', 'reward_type': 'fixed', 'reward_value': 4000.00},
            {'role': 'distributor', 'scene': 'recruit_distributor', 'reward_type': 'fixed', 'reward_value': 2000.00},
            {'role': 'distributor', 'scene': 'team_bonus', 'reward_type': 'percentage', 'reward_value': 0.04},
            {'role': 'user', 'scene': 'recommend', 'reward_type': 'fixed', 'reward_value': 177.60},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM commission_configs")
