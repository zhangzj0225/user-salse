"""seed commission configs v2 — 4 roles, 11 configs per PRD v2

Revision ID: 004
Revises: 003
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    commission_configs = sa.table(
        'commission_configs',
        sa.column('id', sa.Integer),
        sa.column('role', sa.Enum('user', 'member', 'distributor', 'agent')),
        sa.column('scene', sa.String(32)),
        sa.column('reward_type', sa.Enum('fixed', 'percentage')),
        sa.column('reward_value', sa.DECIMAL(10, 4)),
    )

    op.bulk_insert(
        commission_configs,
        [
            # agent (代理)
            {'role': 'agent', 'scene': 'first_reward_888', 'reward_type': 'fixed', 'reward_value': 488.40},
            {'role': 'agent', 'scene': 'first_reward_5000', 'reward_type': 'fixed', 'reward_value': 2750.00},
            {'role': 'agent', 'scene': 'first_reward_10000', 'reward_type': 'fixed', 'reward_value': 5500.00},
            {'role': 'agent', 'scene': 'followup_reward', 'reward_type': 'fixed', 'reward_value': 133.20},
            {'role': 'agent', 'scene': 'team_bonus', 'reward_type': 'percentage', 'reward_value': 0.05},
            # distributor (经销商)
            {'role': 'distributor', 'scene': 'first_reward_888', 'reward_type': 'fixed', 'reward_value': 355.20},
            {'role': 'distributor', 'scene': 'first_reward_5000', 'reward_type': 'fixed', 'reward_value': 2000.00},
            {'role': 'distributor', 'scene': 'first_reward_10000', 'reward_type': 'fixed', 'reward_value': 4000.00},
            {'role': 'distributor', 'scene': 'team_bonus', 'reward_type': 'percentage', 'reward_value': 0.04},
            # member (888会员)
            {'role': 'member', 'scene': 'first_reward_888', 'reward_type': 'fixed', 'reward_value': 177.60},
            # user (普通用户)
            {'role': 'user', 'scene': 'first_reward_888', 'reward_type': 'fixed', 'reward_value': 177.60},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM commission_configs")
