"""End-to-end integration tests for recharge → commission flow (Story 3.4)。

通过 RechargeService.approve_recharge → CommissionEngine.process_recharge
验证完整佣金记账流程。
"""

import pytest
from decimal import Decimal

from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.commission_config import CommissionConfig
from app.models.recharge import Recharge
from app.models.user import User
from app.services.recharge_service import RechargeService


def _seed_commission_configs(db_session):
    """种子佣金配置数据（模拟 migration 004）。"""
    configs = [
        CommissionConfig(role="agent", scene="recharge_888", reward_type="fixed", reward_value=Decimal("488.40")),
        CommissionConfig(role="agent", scene="recharge_5000", reward_type="fixed", reward_value=Decimal("2750.00")),
        CommissionConfig(role="agent", scene="recharge_10000", reward_type="fixed", reward_value=Decimal("5500.00")),
        CommissionConfig(role="agent", scene="followup_reward", reward_type="fixed", reward_value=Decimal("133.20")),
        CommissionConfig(role="distributor", scene="recharge_888", reward_type="fixed", reward_value=Decimal("355.20")),
        CommissionConfig(role="distributor", scene="recharge_5000", reward_type="fixed", reward_value=Decimal("2000.00")),
        CommissionConfig(role="distributor", scene="recharge_10000", reward_type="fixed", reward_value=Decimal("4000.00")),
        CommissionConfig(role="member", scene="recharge_888", reward_type="fixed", reward_value=Decimal("177.60")),
        CommissionConfig(role="user", scene="recharge_888", reward_type="fixed", reward_value=Decimal("177.60")),
    ]
    db_session.add_all(configs)
    db_session.flush()


def _make_admin(db_session):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db_session.add(admin)
    db_session.flush()
    return admin


class TestFirstRewardBooking:
    """AC1-3: 首次奖励记账。"""

    def test_agent_parent_recharge_888(self, db_session):
        """代理上级，下级充 888 → 首次奖励 488.40"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="agent@example.com", role="agent", status="active")
        child = User(email="child@example.com", role="user", status="active", parent_id=None)
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert records[0].user_id == parent.id
        assert Decimal(records[0].amount) == Decimal("488.40")
        assert records[0].source_user_id == child.id

    def test_agent_parent_recharge_5000(self, db_session):
        """代理上级，下级充 5000 → 首次奖励 2750.00"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="agent@example.com", role="agent", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 5000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("2750.00")

    def test_agent_parent_recharge_10000(self, db_session):
        """代理上级，下级充 10000 → 首次奖励 5500.00"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="agent@example.com", role="agent", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 10000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("5500.00")

    def test_distributor_parent_recharge_888(self, db_session):
        """经销商上级，下级充 888 → 首次奖励 355.20"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="dist@example.com", role="distributor", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("355.20")

    def test_member_parent_recharge_888(self, db_session):
        """888 会员上级，下级充 888 → 首次奖励 177.60"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="member@example.com", role="member", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("177.60")

    def test_user_parent_recharge_888(self, db_session):
        """普通用户上级，下级充 888 → 首次奖励 177.60"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="user@example.com", role="user", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("177.60")


class TestNoCommissionScenarios:
    """AC4: 普通用户/888会员推荐的人充 5000/10000 不产生佣金。"""

    def test_member_parent_recharge_5000_no_commission(self, db_session):
        """888 会员上级，下级充 5000 → 无佣金"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="member@example.com", role="member", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 5000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 0

    def test_member_parent_recharge_10000_no_commission(self, db_session):
        """888 会员上级，下级充 10000 → 无佣金"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="member@example.com", role="member", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 10000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 0

    def test_user_parent_recharge_5000_no_commission(self, db_session):
        """普通用户上级，下级充 5000 → 无佣金"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="user@example.com", role="user", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 5000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 0

    def test_no_parent_no_commission(self, db_session):
        """无上级用户充值 → 无佣金"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        user = User(email="noparent@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 0


class TestIdempotency:
    """AC5: 同一笔充值不会重复记账（幂等）。"""

    def test_no_duplicate_commission_on_reapprove(self, db_session):
        """重复批准同一充值不会产生重复佣金（状态机拦截）"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        parent = User(email="agent@example.com", role="agent", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([parent, child])
        db_session.flush()
        child.parent_id = parent.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        # 重复批准应抛出 ValueError
        with pytest.raises(ValueError, match="充值已处理"):
            service.approve_recharge(recharge.id, admin.id, db_session)

        # 仍然只有 1 条佣金记录
        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 1


class TestFollowupReward:
    """AC6: 后续收益（代理→经销商的下级充 888）。"""

    def test_followup_reward_agent_gets_133_20(self, db_session):
        """C 充 888, B 是经销商, A 是代理 → A 获首次奖励 + 后续收益 133.20"""
        _seed_commission_configs(db_session)
        admin = _make_admin(db_session)

        agent = User(email="agent@example.com", role="agent", status="active")
        distributor = User(email="dist@example.com", role="distributor", status="active")
        child = User(email="child@example.com", role="user", status="active")
        db_session.add_all([agent, distributor, child])
        db_session.flush()
        distributor.parent_id = agent.id
        child.parent_id = distributor.id
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        # 应有 2 条佣金记录：首次奖励（经销商获得 355.20）+ 后续收益（代理获得 133.20）
        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id.like(f"recharge_{recharge.id}%"),
        ).all()
        assert len(records) == 2

        first_reward = [r for r in records if r.type == "first_reward"]
        followup = [r for r in records if r.type == "followup_reward"]
        assert len(first_reward) == 1
        assert len(followup) == 1

        # 首次奖励给经销商
        assert first_reward[0].user_id == distributor.id
        assert Decimal(first_reward[0].amount) == Decimal("355.20")

        # 后续收益给代理
        assert followup[0].user_id == agent.id
        assert Decimal(followup[0].amount) == Decimal("133.20")
        assert followup[0].source_user_id == child.id
