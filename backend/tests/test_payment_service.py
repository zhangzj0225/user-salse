"""Tests for app.services.payment_service — 支付订单创建、审核、回调服务。"""

import pytest

from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog
from app.models.payment import Payment
from app.models.user import User
from app.services.payment_service import PaymentService


class TestCreatePayment:
    def test_create_payment_888(self, db_session):
        service = PaymentService()
        payment = service.create_payment(
            email="u888@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )

        assert payment.id is not None
        assert int(payment.amount) == 888
        assert payment.target_role == "member_license"
        assert payment.status == "pending"
        assert payment.user_id is None  # 888 不关联用户

    def test_create_payment_5000(self, db_session):
        service = PaymentService()
        payment = service.create_payment(
            email="u5000@example.com", amount=5000,
            referral_code=None, redirect_url=None, db=db_session,
        )

        assert payment.target_role == "distributor"
        assert payment.status == "pending"

    def test_create_payment_10000(self, db_session):
        service = PaymentService()
        payment = service.create_payment(
            email="u10000@example.com", amount=10000,
            referral_code=None, redirect_url=None, db=db_session,
        )

        assert payment.target_role == "agent"
        assert payment.status == "pending"

    def test_create_payment_invalid_amount(self, db_session):
        service = PaymentService()
        with pytest.raises(ValueError, match="支付金额"):
            service.create_payment(
                email="invalid@example.com", amount=100,
                referral_code=None, redirect_url=None, db=db_session,
            )

    def test_create_payment_existing_user_can_pay_again(self, db_session):
        """5000/10000 支付时已有用户可以再次支付（升级角色）"""
        existing = User(email="dup@example.com", role="distributor", status="active")
        db_session.add(existing)
        db_session.flush()

        service = PaymentService()
        payment = service.create_payment(
            email="dup@example.com", amount=10000,
            referral_code=None, redirect_url=None, db=db_session,
        )
        assert payment.target_role == "agent"
        assert payment.email == "dup@example.com"

    def test_create_payment_duplicate_pending(self, db_session):
        """同邮箱已有 pending 支付时拒绝创建"""
        service = PaymentService()
        service.create_payment(
            email="pending@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        with pytest.raises(ValueError, match="待处理"):
            service.create_payment(
                email="pending@example.com", amount=5000,
                referral_code=None, redirect_url=None, db=db_session,
            )


class TestApprovePayment:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_approve_888_generates_license(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="a888@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        db_session.refresh(payment)
        assert payment.status == "paid"
        assert payment.license_code is not None
        assert payment.channel == "offline"

    def test_approve_5000_creates_distributor(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="a5000@example.com", amount=5000,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        db_session.refresh(payment)
        assert payment.status == "paid"
        user = db_session.query(User).filter(User.email == "a5000@example.com").first()
        assert user is not None
        assert user.role == "distributor"
        assert user.account_quota == 11

    def test_approve_10000_creates_agent(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="a10000@example.com", amount=10000,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        db_session.refresh(payment)
        assert payment.status == "paid"
        user = db_session.query(User).filter(User.email == "a10000@example.com").first()
        assert user is not None
        assert user.role == "agent"
        assert user.account_quota == 22

    def test_approve_writes_audit(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="audit@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "payment_approve",
            AuditLog.target_id == payment.id,
        ).all()
        assert len(logs) == 1

    def test_approve_already_processed(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="processed@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        with pytest.raises(ValueError, match="已处理"):
            service.approve_payment(payment.id, admin.id, db_session)

    def test_approve_nonexistent(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        with pytest.raises(ValueError, match="不存在"):
            service.approve_payment(9999, admin.id, db_session)


class TestRejectPayment:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_reject_success(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="reject@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.reject_payment(payment.id, admin.id, "未收到款项", db_session)

        db_session.refresh(payment)
        assert payment.status == "failed"
        assert payment.reject_reason == "未收到款项"

    def test_reject_writes_audit(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="reject_audit@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.reject_payment(payment.id, admin.id, "测试拒绝", db_session)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "payment_reject",
            AuditLog.target_id == payment.id,
        ).all()
        assert len(logs) == 1

    def test_reject_already_processed(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        payment = service.create_payment(
            email="reject_done@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.reject_payment(payment.id, admin.id, "拒绝", db_session)

        with pytest.raises(ValueError, match="已处理"):
            service.reject_payment(payment.id, admin.id, "再拒绝", db_session)


class TestListPayments:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_list_user_payments(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        # 888 不关联用户，需 approve 后才有 user_id（仅 5000/10000）
        p1 = service.create_payment(
            email="list@example.com", amount=5000,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(p1.id, admin.id, db_session)

        user = db_session.query(User).filter(User.email == "list@example.com").first()
        payments = service.list_user_payments(user.id, db_session)
        assert len(payments) == 1

    def test_list_payments_with_status_filter(self, db_session):
        admin = self._make_admin(db_session)
        service = PaymentService()
        p1 = service.create_payment(
            email="filter1@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(p1.id, admin.id, db_session)
        p2 = service.create_payment(
            email="filter2@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )

        pending, pending_total = service.list_payments(db_session, status="pending")
        assert len(pending) == 1
        assert pending[0].id == p2.id

        all_payments, all_total = service.list_payments(db_session)
        assert len(all_payments) == 2


class TestPaymentDedup:
    """BH-5 pending 去重。"""

    def test_cannot_create_second_pending_payment(self, db_session):
        """同邮箱已有 pending 支付时，新建被拒。"""
        service = PaymentService()
        service.create_payment(
            email="dedup@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        with pytest.raises(ValueError, match="待处理"):
            service.create_payment(
                email="dedup@example.com", amount=5000,
                referral_code=None, redirect_url=None, db=db_session,
            )

    def test_can_create_after_first_approved(self, db_session):
        """第一笔 approve 后可建第二笔。"""
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()

        service = PaymentService()
        p1 = service.create_payment(
            email="seq@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(p1.id, admin.id, db_session)
        # approve 后无 pending，可建第二笔
        p2 = service.create_payment(
            email="seq@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        assert p2.status == "pending"
