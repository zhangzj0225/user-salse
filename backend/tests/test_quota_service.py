"""Tests for app.services.quota_service — 可售额度管理服务。"""

import pytest

from app.models.recharge import Recharge
from app.models.user import User
from app.services.quota_service import QuotaService


class TestGetQuotaInfo:
    def test_agent_with_quota(self, db_session):
        user = User(email="agent@example.com", role="agent", status="active",
                    account_quota=22, account_used=5)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        info = service.get_quota_info(user.id, db_session)

        assert info["role"] == "agent"
        assert info["account_quota"] == 22
        assert info["account_used"] == 5
        assert info["remaining"] == 17
        assert info["can_replenish"] is False

    def test_distributor_with_quota(self, db_session):
        user = User(email="dist@example.com", role="distributor", status="active",
                    account_quota=11, account_used=3)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        info = service.get_quota_info(user.id, db_session)

        assert info["role"] == "distributor"
        assert info["remaining"] == 8

    def test_zero_quota_shows_replenish(self, db_session):
        user = User(email="zero@example.com", role="agent", status="active",
                    account_quota=0, account_used=0)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        info = service.get_quota_info(user.id, db_session)

        assert info["remaining"] == 0
        assert info["can_replenish"] is True

    def test_non_eligible_role_user(self, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        with pytest.raises(ValueError, match="无权访问"):
            service.get_quota_info(user.id, db_session)

    def test_non_eligible_role_member(self, db_session):
        user = User(email="member@example.com", role="member", status="active")
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        with pytest.raises(ValueError, match="无权访问"):
            service.get_quota_info(user.id, db_session)

    def test_nonexistent_user(self, db_session):
        service = QuotaService()
        with pytest.raises(ValueError, match="不存在"):
            service.get_quota_info(9999, db_session)

    def test_sales_records_with_data(self, db_session):
        """验证 sales_records 返回已批准的下级充值记录"""
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=22, account_used=2)
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([agent, child])
        db_session.flush()
        child.parent_id = agent.id
        db_session.flush()

        # 创建 2 条已批准充值 + 1 条 pending（不应出现）
        from datetime import datetime, timezone
        r1 = Recharge(user_id=child.id, amount=888, status="approved",
                      target_role="member", reviewed_at=datetime.now(timezone.utc))
        r2 = Recharge(user_id=child.id, amount=5000, status="approved",
                      target_role="distributor", reviewed_at=datetime.now(timezone.utc))
        r3 = Recharge(user_id=child.id, amount=10000, status="pending",
                      target_role="agent")
        db_session.add_all([r1, r2, r3])
        db_session.flush()

        service = QuotaService()
        info = service.get_quota_info(agent.id, db_session)

        assert len(info["sales_records"]) == 2
        amounts = {r["amount"] for r in info["sales_records"]}
        assert amounts == {"888", "5000"}
        for r in info["sales_records"]:
            assert r["child_email"] == "child@example.com"
            assert r["approved_at"] is not None


class TestCheckQuotaAvailability:
    def test_has_enough_quota(self, db_session):
        user = User(email="enough@example.com", role="agent", status="active",
                    account_quota=5, account_used=2)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        assert service.check_quota_available(user.id, 1, db_session) is True

    def test_not_enough_quota(self, db_session):
        user = User(email="notenough@example.com", role="agent", status="active",
                    account_quota=2, account_used=2)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        assert service.check_quota_available(user.id, 1, db_session) is False

    def test_zero_quota(self, db_session):
        user = User(email="zeroq@example.com", role="agent", status="active",
                    account_quota=0, account_used=0)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        assert service.check_quota_available(user.id, 1, db_session) is False


class TestConsumeQuota:
    def test_consume_success(self, db_session):
        user = User(email="consume@example.com", role="agent", status="active",
                    account_quota=5, account_used=2)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        service.consume_quota(user.id, 1, db_session)

        db_session.refresh(user)
        assert user.account_used == 3

    def test_consume_updates_remaining(self, db_session):
        """S6: 验证 remaining 字段值"""
        user = User(email="remaining@example.com", role="agent", status="active",
                    account_quota=5, account_used=2)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        service.consume_quota(user.id, 2, db_session)

        info = service.get_quota_info(user.id, db_session)
        assert info["remaining"] == 1
        assert info["can_replenish"] is False

    def test_consume_not_enough(self, db_session):
        user = User(email="over@example.com", role="agent", status="active",
                    account_quota=2, account_used=2)
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        with pytest.raises(ValueError, match="额度不足"):
            service.consume_quota(user.id, 1, db_session)

    def test_consume_non_eligible_role(self, db_session):
        user = User(email="noaccess@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = QuotaService()
        with pytest.raises(ValueError, match="无权"):
            service.consume_quota(user.id, 1, db_session)
