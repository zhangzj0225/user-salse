"""add fk on invite_codes.used_by -> users.id

Revision ID: 005
Revises: 004
Create Date: 2026-06-19

Changes:
- invite_codes.used_by: add ForeignKey("users.id") for referential integrity.
  Previously a bare Integer column with no constraint, so a stale used_by
  could point at a deleted user. Uses batch mode so SQLite (no ALTER TABLE
  ADD CONSTRAINT) is handled via table recreation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('invite_codes', schema=None) as batch_op:
        batch_op.alter_column(
            'used_by',
            existing_type=sa.Integer(),
            existing_nullable=True,
            existing_server_default=None,
        )
        batch_op.create_foreign_key(
            'fk_invite_codes_used_by_users',
            'users',
            ['used_by'],
            ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('invite_codes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invite_codes_used_by_users', type_='foreignkey')
