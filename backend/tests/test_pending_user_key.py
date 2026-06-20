"""Tests for D5: DB-level TOCTOU prevention via pending_user_key UNIQUE constraint."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.recharge import Recharge
from app.models.user import User
from app.services.recharge_service import RechargeService


def _make_user(db):
    u = User(email="user@example.com", role="user", status="active")
    db.add(u)
    db.flush()
    return u


class TestPendingUserKeyConstraint:
    """D5: pending_user_key UNIQUE 约束在 DB 级防止同一用户多笔 pending。"""

    def test_duplicate_pending_rejected_by_db(self, db_session):
        """直接插入两条 pending（同 user_id）→ 第二条抛 IntegrityError"""
        user = _make_user(db_session)

        r1 = Recharge(
            user_id=user.id, amount=888, target_role="member",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Recharge(
            user_id=user.id, amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_approved_then_new_pending_allowed(self, db_session):
        """approved 后 pending_user_key=NULL，可再创建新 pending"""
        user = _make_user(db_session)

        r1 = Recharge(
            user_id=user.id, amount=888, target_role="member",
            status="approved", pending_user_key=None,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Recharge(
            user_id=user.id, amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        db_session.flush()  # 不抛异常
        assert r2.id is not None

    def test_rejected_then_new_pending_allowed(self, db_session):
        """rejected 后 pending_user_key=NULL，可再创建新 pending"""
        user = _make_user(db_session)

        r1 = Recharge(
            user_id=user.id, amount=888, target_role="member",
            status="rejected", pending_user_key=None,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Recharge(
            user_id=user.id, amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        db_session.flush()
        assert r2.id is not None

    def test_different_users_pending_allowed(self, db_session):
        """不同用户可同时有 pending"""
        u1 = User(email="u1@example.com", role="user", status="active")
        u2 = User(email="u2@example.com", role="user", status="active")
        db_session.add_all([u1, u2])
        db_session.flush()

        r1 = Recharge(
            user_id=u1.id, amount=888, target_role="member",
            status="pending", pending_user_key=u1.id,
        )
        r2 = Recharge(
            user_id=u2.id, amount=888, target_role="member",
            status="pending", pending_user_key=u2.id,
        )
        db_session.add_all([r1, r2])
        db_session.flush()
        assert r1.id is not None
        assert r2.id is not None

    def test_service_approve_clears_key(self, db_session):
        """approve 后 pending_user_key 被清除"""
        from app.models.admin_user import AdminUser
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        user = _make_user(db_session)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        assert recharge.pending_user_key == user.id

        service.approve_recharge(recharge.id, admin.id, db_session)
        db_session.refresh(recharge)
        assert recharge.pending_user_key is None

    def test_service_reject_clears_key(self, db_session):
        """reject 后 pending_user_key 被清除"""
        from app.models.admin_user import AdminUser
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        user = _make_user(db_session)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        assert recharge.pending_user_key == user.id

        service.reject_recharge(recharge.id, admin.id, "test", db_session)
        db_session.refresh(recharge)
        assert recharge.pending_user_key is None

    def test_service_creates_with_key(self, db_session):
        """create_recharge 设置 pending_user_key = user_id"""
        user = _make_user(db_session)
        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        assert recharge.pending_user_key == user.id
