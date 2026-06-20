"""add pending_user_key to recharges (D5 TOCTOU prevention)

Revision ID: 006
Revises: 005
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D5: 添加 pending_user_key 列 + UNIQUE 约束
    # pending 时 = user_id，非 pending 时 = NULL。UNIQUE 下 NULL 不冲突，仅 pending 互斥。
    op.add_column('recharges', sa.Column('pending_user_key', sa.Integer(), nullable=True))

    # 回填：将现有 pending 记录的 pending_user_key 设为 user_id
    op.execute("UPDATE recharges SET pending_user_key = user_id WHERE status = 'pending'")

    op.create_unique_constraint('uq_recharges_pending_user', 'recharges', ['pending_user_key'])


def downgrade() -> None:
    op.drop_constraint('uq_recharges_pending_user', 'recharges', type_='unique')
    op.drop_column('recharges', 'pending_user_key')
