"""Tests for app.services.sale_service — 额度销售（场景 A）。"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.commission_record import CommissionRecord
from app.models.email_verification_code import EmailVerificationCode
from app.models.payment import Payment
from app.models.user import User
from app.services.sale_service import SaleService

MOCK_CODE = "123456"


def _make_seller(db, email="agent@example.com", role="agent", quota=5, used=0):
    u = User(email=email, role=role, status="active",
             account_quota=quota, account_used=used)
    db.add(u)
    db.flush()
    return u


def _make_code(db, email, scene="sale_verify", code=MOCK_CODE):
    record = EmailVerificationCode(
        email=email,
        code=code,
        scene=scene,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(record)
    db.flush()
    return record


class TestSellAccount:
    def test_sell_success(self, db_session):
        """正常销售流程"""
        seller = _make_seller(db_session, quota=5, used=0)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        result = service.sell_account(
            seller.id, "customer@example.com", MOCK_CODE, db_session
        )

        # 验证返回值
        assert result["customer_id"] is not None
        assert result["payment_id"] is not None
        assert result["remaining_quota"] == 4

        # 验证客户创建
        customer = db_session.query(User).filter(User.id == result["customer_id"]).first()
        assert customer.email == "customer@example.com"
        assert customer.role == "distributor"
        assert customer.parent_id == seller.id

        # 验证额度消耗
        db_session.refresh(seller)
        assert seller.account_used == 1
        assert seller.account_quota - seller.account_used == 4

        # 验证 Payment 记录
        payment = db_session.query(Payment).filter(Payment.id == result["payment_id"]).first()
        assert payment.amount == Decimal("888.00")
        assert payment.status == "paid"
        assert payment.target_role == "member_license"
        assert payment.reviewed_by is None

        # 验证审计日志
        log = db_session.query(AuditLog).filter(AuditLog.action == "quota_sale").first()
        assert log is not None
        assert log.operator_id == seller.id
        assert log.target_id == customer.id

    def test_no_commission_generated(self, db_session):
        """AC: 场景 A 不产生任何佣金"""
        seller = _make_seller(db_session)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        result = service.sell_account(
            seller.id, "customer@example.com", MOCK_CODE, db_session
        )

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"sale_{result['payment_id']}"
        ).all()
        assert len(records) == 0

    def test_distributor_can_sell(self, db_session):
        """经销商也可以销售"""
        seller = _make_seller(db_session, email="dist@example.com", role="distributor", quota=11)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        result = service.sell_account(
            seller.id, "customer@example.com", MOCK_CODE, db_session
        )
        assert result["remaining_quota"] == 10

    def test_zero_quota_cannot_sell(self, db_session):
        """额度为 0 不可销售"""
        seller = _make_seller(db_session, quota=1, used=1)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        with pytest.raises(ValueError, match="额度不足"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

    def test_duplicate_email_rejected(self, db_session):
        """客户邮箱已注册"""
        seller = _make_seller(db_session)
        existing = User(email="taken@example.com", role="distributor", status="active")
        db_session.add(existing)
        db_session.flush()
        _make_code(db_session, "taken@example.com")

        service = SaleService()
        with pytest.raises(ValueError, match="已注册"):
            service.sell_account(seller.id, "taken@example.com", MOCK_CODE, db_session)

    def test_invalid_verification_code(self, db_session):
        """S2: 验证码错误"""
        seller = _make_seller(db_session)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        with pytest.raises(ValueError, match="验证码"):
            service.sell_account(seller.id, "customer@example.com", "000000", db_session)

    def test_no_verification_code_record(self, db_session):
        """S2: 未发送验证码"""
        seller = _make_seller(db_session)
        service = SaleService()
        with pytest.raises(ValueError, match="验证码"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

    def test_email_normalized_lower(self, db_session):
        """邮箱统一小写"""
        seller = _make_seller(db_session)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        result = service.sell_account(
            seller.id, "Customer@Example.COM", MOCK_CODE, db_session
        )

        customer = db_session.query(User).filter(User.id == result["customer_id"]).first()
        assert customer.email == "customer@example.com"

    def test_nonexistent_seller(self, db_session):
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        with pytest.raises(ValueError, match="不存在"):
            service.sell_account(9999, "customer@example.com", MOCK_CODE, db_session)

    def test_sales_record_visible_in_quota(self, db_session):
        """销售后额度页面的 sales_records 可见"""
        seller = _make_seller(db_session, quota=5, used=0)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        service.sell_account(
            seller.id, "customer@example.com", MOCK_CODE, db_session
        )

        from app.services.quota_service import QuotaService
        quota_service = QuotaService()
        info = quota_service.get_quota_info(seller.id, db_session)

        assert len(info["sales_records"]) == 1
        assert info["sales_records"][0]["amount"] == "888.00"

    def test_quota_not_consumed_on_failure(self, db_session):
        """M2: 销售失败时额度不消耗"""
        seller = _make_seller(db_session, quota=5, used=0)
        service = SaleService()
        with pytest.raises(ValueError, match="验证码"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

        db_session.refresh(seller)
        assert seller.account_used == 0  # 额度未消耗
