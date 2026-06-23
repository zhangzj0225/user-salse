"""Tests for D5: DB-level TOCTOU prevention via pending_user_key UNIQUE constraint."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.payment import Payment
from app.models.user import User
from app.services.payment_service import PaymentService


def _make_user(db):
    u = User(email="user@example.com", role="distributor", status="active")
    db.add(u)
    db.flush()
    return u


class TestPendingUserKeyConstraint:
    """D5: pending_user_key UNIQUE 约束在 DB 级防止同一用户多笔 pending。"""

    def test_duplicate_pending_rejected_by_db(self, db_session):
        """直接插入两条 pending（同 user_id）→ 第二条抛 IntegrityError"""
        user = _make_user(db_session)

        r1 = Payment(
            user_id=user.id, email="user@example.com", amount=888, target_role="member_license",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Payment(
            user_id=user.id, email="user@example.com", amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_paid_then_new_pending_allowed(self, db_session):
        """paid 后 pending_user_key=NULL，可再创建新 pending"""
        user = _make_user(db_session)

        r1 = Payment(
            user_id=user.id, email="user@example.com", amount=888, target_role="member_license",
            status="paid", pending_user_key=None,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Payment(
            user_id=user.id, email="user@example.com", amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        db_session.flush()  # 不抛异常
        assert r2.id is not None

    def test_failed_then_new_pending_allowed(self, db_session):
        """failed 后 pending_user_key=NULL，可再创建新 pending"""
        user = _make_user(db_session)

        r1 = Payment(
            user_id=user.id, email="user@example.com", amount=888, target_role="member_license",
            status="failed", pending_user_key=None,
        )
        db_session.add(r1)
        db_session.flush()

        r2 = Payment(
            user_id=user.id, email="user@example.com", amount=5000, target_role="distributor",
            status="pending", pending_user_key=user.id,
        )
        db_session.add(r2)
        db_session.flush()
        assert r2.id is not None

    def test_different_users_pending_allowed(self, db_session):
        """不同用户可同时有 pending"""
        u1 = User(email="u1@example.com", role="distributor", status="active")
        u2 = User(email="u2@example.com", role="distributor", status="active")
        db_session.add_all([u1, u2])
        db_session.flush()

        r1 = Payment(
            user_id=u1.id, email="u1@example.com", amount=888, target_role="member_license",
            status="pending", pending_user_key=u1.id,
        )
        r2 = Payment(
            user_id=u2.id, email="u2@example.com", amount=888, target_role="member_license",
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

        service = PaymentService()
        payment = service.create_payment(
            email="user@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )

        service.approve_payment(payment.id, admin.id, db_session)
        db_session.refresh(payment)
        assert payment.pending_user_key is None

    def test_service_reject_clears_key(self, db_session):
        """reject 后 pending_user_key 被清除"""
        from app.models.admin_user import AdminUser
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        user = _make_user(db_session)
        db_session.flush()

        service = PaymentService()
        payment = service.create_payment(
            email="user@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )

        service.reject_payment(payment.id, admin.id, "test", db_session)
        db_session.refresh(payment)
        assert payment.pending_user_key is None
