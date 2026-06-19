"""Tests for app.services.sale_service — 额度销售（场景 A）。"""

import pytest
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.commission_record import CommissionRecord
from app.models.recharge import Recharge
from app.models.user import User
from app.services.sale_service import SaleService


def _make_seller(db, email="agent@example.com", role="agent", quota=5, used=0):
    u = User(email=email, role=role, status="active",
             account_quota=quota, account_used=used)
    db.add(u)
    db.flush()
    return u


class TestSellAccount:
    def test_sell_success(self, db_session):
        """正常销售流程"""
        seller = _make_seller(db_session, quota=5, used=0)
        service = SaleService()
        result = service.sell_account(seller.id, "customer@example.com", db_session)

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
        assert recharge.amount == Decimal("888")
        assert recharge.status == "approved"
        assert recharge.target_role == "member"

        # 验证审计日志
        log = db_session.query(AuditLog).filter(AuditLog.action == "quota_sale").first()
        assert log is not None
        assert log.operator_id == seller.id
        assert log.target_id == customer.id

    def test_no_commission_generated(self, db_session):
        """AC: 场景 A 不产生任何佣金"""
        seller = _make_seller(db_session)
        service = SaleService()
        result = service.sell_account(seller.id, "customer@example.com", db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"sale_{result['recharge_id']}"
        ).all()
        assert len(records) == 0

    def test_distributor_can_sell(self, db_session):
        """经销商也可以销售"""
        seller = _make_seller(db_session, email="dist@example.com", role="distributor", quota=11)
        service = SaleService()
        result = service.sell_account(seller.id, "customer@example.com", db_session)

        assert result["remaining_quota"] == 10

    def test_user_cannot_sell(self, db_session):
        """普通用户无权销售"""
        seller = _make_seller(db_session, email="user@example.com", role="user", quota=0)
        service = SaleService()
        with pytest.raises(ValueError, match="无权销售"):
            service.sell_account(seller.id, "customer@example.com", db_session)

    def test_member_cannot_sell(self, db_session):
        """888 会员无权销售"""
        seller = _make_seller(db_session, email="member@example.com", role="member", quota=0)
        service = SaleService()
        with pytest.raises(ValueError, match="无权销售"):
            service.sell_account(seller.id, "customer@example.com", db_session)

    def test_zero_quota_cannot_sell(self, db_session):
        """额度为 0 不可销售"""
        seller = _make_seller(db_session, quota=1, used=1)
        service = SaleService()
        with pytest.raises(ValueError, match="额度不足"):
            service.sell_account(seller.id, "customer@example.com", db_session)

    def test_duplicate_email_rejected(self, db_session):
        """客户邮箱已注册"""
        seller = _make_seller(db_session)
        existing = User(email="taken@example.com", role="user", status="active")
        db_session.add(existing)
        db_session.flush()

        service = SaleService()
        with pytest.raises(ValueError, match="已注册"):
            service.sell_account(seller.id, "taken@example.com", db_session)

    def test_email_normalized_lower(self, db_session):
        """邮箱统一小写"""
        seller = _make_seller(db_session)
        service = SaleService()
        result = service.sell_account(seller.id, "Customer@Example.COM", db_session)

        customer = db_session.query(User).filter(User.id == result["customer_id"]).first()
        assert customer.email == "customer@example.com"

    def test_nonexistent_seller(self, db_session):
        service = SaleService()
        with pytest.raises(ValueError, match="不存在"):
            service.sell_account(9999, "customer@example.com", db_session)

    def test_sales_record_visible_in_quota(self, db_session):
        """销售后额度页面的 sales_records 可见"""
        seller = _make_seller(db_session, quota=5, used=0)
        service = SaleService()
        service.sell_account(seller.id, "customer@example.com", db_session)

        from app.services.quota_service import QuotaService
        quota_service = QuotaService()
        info = quota_service.get_quota_info(seller.id, db_session)

        assert len(info["sales_records"]) == 1
        assert info["sales_records"][0]["amount"] == "888.00"
