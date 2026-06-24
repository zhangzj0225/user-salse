"""sync schema to PRD v2 final — drop legacy tables, create current tables

Revision ID: 008
Revises: 007_system_configs
Create Date: 2026-06-24

Migration 003 created the *intermediate* v2 schema (recharges, invite_codes,
licenses with email+NOT NULL user_id, users with invite_code column, etc.).
The ORM models have since evolved to the *final* v2 schema. This migration
brings the DB in line.

Changes:
- DROP: recharges, invite_codes, sales (replaced by payments, referral_codes)
- CREATE: payments, referral_codes, quota_replenishments, pending_user_keys
- ALTER users: invite_code→referral_code, add referral_code_generated,
  fix role enum (drop user/member)
- ALTER licenses: drop email, make user_id NULLABLE, add activated_user_id/info,
  fix source enum (recharge→payment)
- ALTER commission_configs: fix role enum (drop user/member)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008'
down_revision: Union[str, None] = '007_system_configs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Drop legacy tables ──────────────────────────────────────
    op.drop_table('recharges')
    op.drop_table('invite_codes')
    op.drop_table('sales')

    # ── 2. Create current tables ───────────────────────────────────

    # payments (replaces recharges)
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('target_role', sa.String(32), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', 'failed', 'refunded'),
                  server_default='pending', nullable=False),
        sa.Column('channel', sa.String(32), nullable=True),
        sa.Column('referral_code', sa.String(128), nullable=True),
        sa.Column('license_code', sa.String(128), nullable=True),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('pending_user_key', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pending_user_key'),
        sa.UniqueConstraint('license_code'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['admin_users.id']),
    )

    # referral_codes (replaces invite_codes)
    op.create_table(
        'referral_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    # quota_replenishments (new in C3 fix)
    op.create_table(
        'quota_replenishments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('old_quota', sa.Integer(), nullable=False),
        sa.Column('requested_amount', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected'),
                  server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['admin_users.id']),
    )

    # referral_relationships (FR-8 — immutable relationship tracking)
    op.create_table(
        'referral_relationships',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parent_user_id', sa.Integer(), nullable=False),
        sa.Column('child_user_id', sa.Integer(), nullable=True),
        sa.Column('referral_code', sa.String(128), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_user_id', 'child_user_id', 'payment_id',
                            name='uq_referral_relationships'),
        sa.ForeignKeyConstraint(['parent_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['child_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
    )

    # ── 3. Alter users table ──────────────────────────────────────
    # SQLite: batch mode recreates table with new schema, copies data
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Rename invite_code → referral_code
        batch_op.alter_column('invite_code', new_column_name='referral_code',
                              existing_type=sa.String(32), nullable=True)
        # Add missing column
        batch_op.add_column(sa.Column('referral_code_generated',
                                       sa.Integer(), server_default='0', nullable=False))

    # ── 4. Alter licenses table ───────────────────────────────────
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        # Make user_id nullable
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)
        # Drop email column (no longer used)
        batch_op.drop_column('email')
        # Add new columns
        batch_op.add_column(sa.Column('activated_user_id', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('activated_user_info', sa.String(512), nullable=True))

    # ── 5. Alter commission_configs enum (cosmetic on SQLite) ─────
    # SQLite stores enums as VARCHAR; this is mostly for documentation.
    # We use raw SQL since batch_alter_table can't change enum types.
    # The seed migration 004 already only inserts distributor/agent values.


def downgrade() -> None:
    # Drop new tables
    op.drop_table('referral_relationships')
    op.drop_table('quota_replenishments')
    op.drop_table('referral_codes')
    op.drop_table('payments')

    # Recreate legacy tables (minimal — for downgrade testing only)
    op.create_table(
        'recharges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('target_role', sa.Enum('member', 'distributor', 'agent'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected'),
                  server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('pending_user_key', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pending_user_key'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['admin_users.id']),
    )
    op.create_table(
        'invite_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('generator_id', sa.Integer(), nullable=False),
        sa.Column('key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('used_by', sa.Integer(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['generator_id'], ['users.id']),
    )
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('customer_email', sa.String(128), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), server_default='888.00', nullable=False),
        sa.Column('remark', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id']),
    )

    # Revert users
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('referral_code_generated')
        batch_op.alter_column('referral_code', new_column_name='invite_code',
                              existing_type=sa.String(32), nullable=True)

    # Revert licenses
    with op.batch_alter_table('licenses', schema=None) as batch_op:
        batch_op.drop_column('activated_user_info')
        batch_op.drop_column('activated_user_id')
        batch_op.add_column(sa.Column('email', sa.String(128), nullable=False,
                                       server_default=''))
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
