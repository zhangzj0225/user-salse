"""create all tables

Revision ID: 001
Revises:
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('openid', sa.String(64), unique=True, nullable=True),
        sa.Column('phone', sa.String(11), unique=True, nullable=True),
        sa.Column('nickname', sa.String(64), nullable=True),
        sa.Column('avatar_url', sa.String(256), nullable=True),
        sa.Column('role', sa.Enum('user', 'distributor', 'agent'), server_default='user', nullable=False),
        sa.Column('parent_id', sa.BigInteger(), nullable=True),
        sa.Column('invite_code', sa.String(32), unique=True, nullable=True),
        sa.Column('account_quota', sa.Integer(), server_default='0', nullable=False),
        sa.Column('account_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'rejected'), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ),
    )

    # admin_users
    op.create_table(
        'admin_users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(64), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(32), server_default='admin', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # invite_codes
    op.create_table(
        'invite_codes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), unique=True, nullable=False),
        sa.Column('generator_id', sa.BigInteger(), nullable=False),
        sa.Column('target_role', sa.Enum('agent', 'distributor'), nullable=False),
        sa.Column('key_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('used_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['generator_id'], ['users.id'], ),
    )

    # sales
    op.create_table(
        'sales',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_phone', sa.String(11), nullable=False),
        sa.Column('amount', sa.DECIMAL(10, 2), server_default='888.00', nullable=False),
        sa.Column('remark', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ),
    )

    # sms_records
    op.create_table(
        'sms_records',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('phone', sa.String(11), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('scene', sa.String(32), server_default='sale_verify', nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # quota_purchases
    op.create_table(
        'quota_purchases',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected'), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # commission_configs
    op.create_table(
        'commission_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
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
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('type', sa.Enum('first_reward', 'sale_commission', 'team_bonus', 'recommend'), nullable=False),
        sa.Column('source_user_id', sa.BigInteger(), nullable=True),
        sa.Column('business_id', sa.String(64), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # tickets
    op.create_table(
        'tickets',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(256), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', 'rejected'), server_default='pending', nullable=False),
        sa.Column('reject_reason', sa.String(256), nullable=True),
        sa.Column('processed_by', sa.BigInteger(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['processed_by'], ['admin_users.id'], ),
    )

    # audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_type', sa.Enum('system', 'user', 'admin'), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=True),
        sa.Column('target_id', sa.BigInteger(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('business_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # config_change_logs
    op.create_table(
        'config_change_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.BigInteger(), nullable=False),
        sa.Column('config_key', sa.String(64), nullable=False),
        sa.Column('old_value', sa.String(256), nullable=True),
        sa.Column('new_value', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ),
    )

    # notification_logs
    op.create_table(
        'notification_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('sent', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )


def downgrade() -> None:
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
    op.drop_table('admin_users')
    op.drop_table('users')
