"""Tests for app.services.sale_service — 额度销售（场景 A）。"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.commission_record import CommissionRecord
from app.models.email_verification_code import EmailVerificationCode
from app.models.recharge import Recharge
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
        assert result["recharge_id"] is not None
        assert result["remaining_quota"] == 4

        # 验证客户创建
        customer = db_session.query(User).filter(User.id == result["customer_id"]).first()
        assert customer.email == "customer@example.com"
        assert customer.role == "member"
        assert customer.parent_id == seller.id

        # 验证额度消耗
        db_session.refresh(seller)
        assert seller.account_used == 1
        assert seller.account_quota - seller.account_used == 4

        # 验证 Recharge 记录
        recharge = db_session.query(Recharge).filter(Recharge.id == result["recharge_id"]).first()
        assert recharge.amount == Decimal("888.00")
        assert recharge.status == "approved"
        assert recharge.target_role == "member"
        # F2: sale 流程无管理员审核，reviewed_by 留 null（FK 指向 admin_users，
        # 写 seller_id 在生产 MySQL 会 IntegrityError）
        assert recharge.reviewed_by is None

        # 验证审计日志
        log = db_session.query(AuditLog).filter(AuditLog.action == "quota_sale").first()
        assert log is not None
        assert log.operator_id == seller.id
        assert log.target_id == customer.id
        assert log.new_value["amount"] == "888.00"  # S1: 字符串一致

    def test_no_commission_generated(self, db_session):
        """AC: 场景 A 不产生任何佣金"""
        seller = _make_seller(db_session)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        result = service.sell_account(
            seller.id, "customer@example.com", MOCK_CODE, db_session
        )

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"sale_{result['recharge_id']}"
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

    def test_user_cannot_sell(self, db_session):
        """普通用户无权销售"""
        seller = _make_seller(db_session, email="user@example.com", role="user", quota=0)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        with pytest.raises(ValueError, match="无权销售"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

    def test_member_cannot_sell(self, db_session):
        """888 会员无权销售"""
        seller = _make_seller(db_session, email="member@example.com", role="member", quota=0)
        _make_code(db_session, "customer@example.com")
        service = SaleService()
        with pytest.raises(ValueError, match="无权销售"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

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
        existing = User(email="taken@example.com", role="user", status="active")
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
        # 不创建验证码记录 → 验证码校验失败
        service = SaleService()
        with pytest.raises(ValueError, match="验证码"):
            service.sell_account(seller.id, "customer@example.com", MOCK_CODE, db_session)

        db_session.refresh(seller)
        assert seller.account_used == 0  # 额度未消耗
