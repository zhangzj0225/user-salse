"""refactor models v2 — drop old tables, create new tables per PRD v2

Revision ID: 003
Revises: 002
Create Date: 2026-06-18

Changes:
- users: phone→email, remove openid, add member role, status default active, add password_hash
- invite_codes: remove target_role, add used_at
- sales: customer_phone→customer_email
- commission_configs: role enum add member
- commission_records: type enum add followup_reward
- NEW: email_verification_codes, recharges, licenses
- REMOVED: sms_records, quota_purchases
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Drop old tables that are being removed or replaced ---
    op.drop_table('notification_logs')
    op.drop_table('config_change_logs')
    op.drop_table('audit_logs')
    op.drop_table('tickets')
    op.drop_table('commission_records')
    op.drop_table('commission_configs')
    op.drop_table('quota_purchases')
    op.drop_table('sms_records')
    op.drop_table('sales')
    op.drop_table('invite_codes')
    op.drop_table('users')
    # admin_users stays as-is

    # --- Create users (refactored) ---
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=True),
        sa.Column('nickname', sa.String(64), nullable=True),
        sa.Column('avatar_url', sa.String(256), nullable=True),
        sa.Column('role', sa.Enum('user', 'member', 'distributor', 'agent'), server_default='user', nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('invite_code', sa.String(32), nullable=True),
        sa.Column('account_quota', sa.Integer(), server_default='0', nullable=False),
        sa.Column('account_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'rejected'), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('invite_code'),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ),
    )

    # --- Create email_verification_codes (replaces sms_records) ---
    op.create_table(
        'email_verification_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('scene', sa.String(32), server_default='register', nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_email_scene_verified', 'email_verification_codes', ['email', 'scene', 'verified', 'expires_at'])

    # --- Create invite_codes (unified type, no target_role) ---
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
        sa.ForeignKeyConstraint(['generator_id'], ['users.id'], ),
    )

    # --- Create recharges (new) ---
    op.create_table(
        'recharges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('target_role', sa.Enum('member', 'distributor', 'agent'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected'), server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['admin_users.id'], ),
    )

    # --- Create sales (customer_email instead of customer_phone) ---
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('customer_email', sa.String(128), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), server_default='888.00', nullable=False),
        sa.Column('remark', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ),
    )

    # --- Create licenses (new) ---
    op.create_table(
        'licenses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(128), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('source', sa.Enum('recharge', 'sale', 'role_builtin'), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('unused', 'activated', 'expired'), server_default='unused', nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # --- Create commission_configs (4 roles) ---
    op.create_table(
        'commission_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role', sa.Enum('user', 'member', 'distributor', 'agent'), nullable=False),
        sa.Column('scene', sa.String(32), nullable=False),
        sa.Column('reward_type', sa.Enum('fixed', 'percentage'), nullable=False),
        sa.Column('reward_value', sa.DECIMAL(10, 4), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role', 'scene', name='uq_commission_configs_role_scene'),
    )

    # --- Create commission_records (add followup_reward type) ---
    op.create_table(
        'commission_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('type', sa.Enum('first_reward', 'sale_commission', 'team_bonus', 'recommend', 'followup_reward'), nullable=False),
        sa.Column('source_user_id', sa.Integer(), nullable=True),
        sa.Column('business_id', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('business_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # --- Create tickets ---
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(256), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', 'rejected'), server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['processed_by'], ['admin_users.id'], ),
    )

    # --- Recreate audit_logs ---
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=True),
        sa.Column('operator_type', sa.Enum('system', 'user', 'admin'), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('business_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- Recreate config_change_logs ---
    op.create_table(
        'config_change_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(64), nullable=False),
        sa.Column('old_value', sa.String(256), nullable=True),
        sa.Column('new_value', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ),
    )

    # --- Recreate notification_logs ---
    op.create_table(
        'notification_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('sent', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )


def downgrade() -> None:
    # Drop new tables
    op.drop_table('notification_logs')
    op.drop_table('config_change_logs')
    op.drop_table('audit_logs')
    op.drop_table('tickets')
    op.drop_table('commission_records')
    op.drop_table('commission_configs')
    op.drop_table('licenses')
    op.drop_table('sales')
    op.drop_table('recharges')
    op.drop_table('invite_codes')
    op.drop_index('idx_email_scene_verified', table_name='email_verification_codes')
    op.drop_table('email_verification_codes')
    op.drop_table('users')

    # Recreate old tables (Epic 1 schema)
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('openid', sa.String(64), nullable=True),
        sa.Column('phone', sa.String(11), nullable=True),
        sa.Column('nickname', sa.String(64), nullable=True),
        sa.Column('avatar_url', sa.String(256), nullable=True),
        sa.Column('role', sa.Enum('user', 'distributor', 'agent'), server_default='user', nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('invite_code', sa.String(32), nullable=True),
        sa.Column('account_quota', sa.Integer(), server_default='0', nullable=False),
        sa.Column('account_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'rejected'), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('openid'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('invite_code'),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ),
    )
    op.create_table(
        'invite_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('generator_id', sa.Integer(), nullable=False),
        sa.Column('target_role', sa.Enum('agent', 'distributor'), nullable=False),
        sa.Column('key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('used_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['generator_id'], ['users.id'], ),
    )
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('customer_phone', sa.String(11), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), server_default='888.00', nullable=False),
        sa.Column('remark', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ),
    )
    op.create_table(
        'sms_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('phone', sa.String(11), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('scene', sa.String(32), server_default='sale_verify', nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'quota_purchases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected'), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_table(
        'commission_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role', sa.Enum('agent', 'distributor', 'user'), nullable=False),
        sa.Column('scene', sa.String(32), nullable=False),
        sa.Column('reward_type', sa.Enum('fixed', 'percentage'), nullable=False),
        sa.Column('reward_value', sa.DECIMAL(10, 4), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role', 'scene', name='uq_commission_configs_role_scene'),
    )
    op.create_table(
        'commission_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('type', sa.Enum('first_reward', 'sale_commission', 'team_bonus', 'recommend'), nullable=False),
        sa.Column('source_user_id', sa.Integer(), nullable=True),
        sa.Column('business_id', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('business_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(256), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', 'rejected'), server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['processed_by'], ['admin_users.id'], ),
    )
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=True),
        sa.Column('operator_type', sa.Enum('system', 'user', 'admin'), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('business_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'config_change_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(64), nullable=False),
        sa.Column('old_value', sa.String(256), nullable=True),
        sa.Column('new_value', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ),
    )
    op.create_table(
        'notification_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('sent', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
