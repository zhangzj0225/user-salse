"""End-to-end integration tests for scenario B commission (Story 3.8)。

场景 B：下级自己充值 → 上级获得佣金（首次奖励 + 后续收益）。
与 Story 3.4 的区别：3.4 验证种子数据一致性，3.8 验证场景 B 全链路 + 幂等 + business_id 格式 + 审计日志。
"""

import pytest
from decimal import Decimal

from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog
from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.recharge_service import RechargeService


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.flush()
    return admin


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


class TestFirstRewardScenarioB:
    """AC1-2: 场景 B 首次奖励。"""

    @pytest.mark.parametrize("parent_role,amount,expected", [
        ("agent", 888, Decimal("488.40")),
        ("agent", 5000, Decimal("2750.00")),
        ("agent", 10000, Decimal("5500.00")),
        ("distributor", 888, Decimal("355.20")),
        ("distributor", 5000, Decimal("2000.00")),
        ("distributor", 10000, Decimal("4000.00")),
        ("user", 888, Decimal("177.60")),
        ("member", 888, Decimal("177.60")),
    ])
    def test_first_reward_all_combinations(self, db_session, seed_commission_configs,
                                           parent_role, amount, expected):
        """验证所有首次奖励组合"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", parent_role)
        child = _make_user(db_session, "child@example.com", parent_id=parent.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, amount, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        record = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
            CommissionRecord.type == "first_reward",
        ).first()
        assert record is not None
        assert record.user_id == parent.id
        assert Decimal(record.amount) == expected
        assert record.source_user_id == child.id

    @pytest.mark.parametrize("parent_role,amount", [
        ("user", 5000),
        ("user", 10000),
        ("member", 5000),
        ("member", 10000),
    ])
    def test_no_commission_for_user_member_higher_amounts(
        self, db_session, seed_commission_configs, parent_role, amount
    ):
        """AC: 普通用户/888会员推荐的人充 5000/10000 不产生佣金"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", parent_role)
        child = _make_user(db_session, "child@example.com", parent_id=parent.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, amount, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 0


class TestFollowupRewardScenarioB:
    """AC3-4: 后续收益（代理→经销商→下下级充 888）。"""

    def test_followup_business_id_format(self, db_session, seed_commission_configs):
        """AC4: 后续收益 business_id = "recharge_{下下级充值id}_followup_{A的ID}" """
        admin = _make_admin(db_session)
        agent = _make_user(db_session, "agent@example.com", "agent")
        distributor = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "child@example.com", parent_id=distributor.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        expected_bid = f"recharge_{recharge.id}_followup_{agent.id}"
        record = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == expected_bid,
        ).first()
        assert record is not None
        assert record.type == "followup_reward"
        assert Decimal(record.amount) == Decimal("133.20")
        assert record.user_id == agent.id
        assert record.source_user_id == child.id

    def test_no_followup_when_parent_is_distributor(self, db_session, seed_commission_configs):
        """上级是经销商 → 无后续收益（只有代理才有）"""
        admin = _make_admin(db_session)
        distributor = _make_user(db_session, "dist@example.com", "distributor")
        mid = _make_user(db_session, "mid@example.com", "user", parent_id=distributor.id)
        child = _make_user(db_session, "child@example.com", parent_id=mid.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        followup = db_session.query(CommissionRecord).filter(
            CommissionRecord.type == "followup_reward",
        ).all()
        assert len(followup) == 0

    def test_no_followup_for_5000_or_10000(self, db_session, seed_commission_configs):
        """后续收益仅在充 888 时触发"""
        admin = _make_admin(db_session)
        agent = _make_user(db_session, "agent@example.com", "agent")
        distributor = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "child@example.com", parent_id=distributor.id)

        for amount in (5000, 10000):
            service = RechargeService()
            recharge = service.create_recharge(child.id, amount, db_session)
            service.approve_recharge(recharge.id, admin.id, db_session)

        followup = db_session.query(CommissionRecord).filter(
            CommissionRecord.type == "followup_reward",
        ).all()
        assert len(followup) == 0


class TestIdempotency:
    """AC5: 幂等保护。"""

    def test_first_reward_idempotent(self, db_session, seed_commission_configs):
        """重复批准不会产生重复首次奖励"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=parent.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        with pytest.raises(ValueError, match="充值已处理"):
            service.approve_recharge(recharge.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}",
        ).all()
        assert len(records) == 1

    def test_followup_idempotent(self, db_session, seed_commission_configs):
        """后续收益 business_id 幂等"""
        admin = _make_admin(db_session)
        agent = _make_user(db_session, "agent@example.com", "agent")
        distributor = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "child@example.com", parent_id=distributor.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        with pytest.raises(ValueError, match="充值已处理"):
            service.approve_recharge(recharge.id, admin.id, db_session)

        followup = db_session.query(CommissionRecord).filter(
            CommissionRecord.type == "followup_reward",
            CommissionRecord.business_id == f"recharge_{recharge.id}_followup_{agent.id}",
        ).all()
        assert len(followup) == 1


class TestAuditLog:
    """AC6: 审计日志。"""

    def test_recharge_approve_audit_log(self, db_session, seed_commission_configs):
        """充值批准写入审计日志"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=parent.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        log = db_session.query(AuditLog).filter(
            AuditLog.action == "recharge_approve",
            AuditLog.business_id == f"recharge_{recharge.id}",
        ).first()
        assert log is not None
        assert log.operator_type == "admin"
        assert log.target_type == "recharge"
        assert log.target_id == recharge.id


class TestFullChainScenarioB:
    """完整链路：A(代理) → B(经销商) → C(普通用户) 充 888。"""

    def test_full_chain_recharge_888(self, db_session, seed_commission_configs):
        """C 充 888 → B 获首次奖励 355.20 + A 获后续收益 133.20"""
        admin = _make_admin(db_session)
        agent = _make_user(db_session, "a@example.com", "agent")
        distributor = _make_user(db_session, "b@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "c@example.com", parent_id=distributor.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        all_records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id.like(f"recharge_{recharge.id}%"),
        ).all()
        assert len(all_records) == 2

        first = next(r for r in all_records if r.type == "first_reward")
        followup = next(r for r in all_records if r.type == "followup_reward")

        assert Decimal(first.amount) == Decimal("355.20")
        assert first.user_id == distributor.id
        assert Decimal(followup.amount) == Decimal("133.20")
        assert followup.user_id == agent.id

    def test_multiple_followup_rewards(self, db_session, seed_commission_configs):
        """代理的多个经销商下级各自推荐充 888 → 代理获多笔后续收益"""
        admin = _make_admin(db_session)
        agent = _make_user(db_session, "a@example.com", "agent")
        dist1 = _make_user(db_session, "b1@example.com", "distributor", parent_id=agent.id)
        dist2 = _make_user(db_session, "b2@example.com", "distributor", parent_id=agent.id)
        c1 = _make_user(db_session, "c1@example.com", parent_id=dist1.id)
        c2 = _make_user(db_session, "c2@example.com", parent_id=dist2.id)

        service = RechargeService()
        r1 = service.create_recharge(c1.id, 888, db_session)
        service.approve_recharge(r1.id, admin.id, db_session)
        r2 = service.create_recharge(c2.id, 888, db_session)
        service.approve_recharge(r2.id, admin.id, db_session)

        followups = db_session.query(CommissionRecord).filter(
            CommissionRecord.type == "followup_reward",
            CommissionRecord.user_id == agent.id,
        ).all()
        assert len(followups) == 2
        for f in followups:
            assert Decimal(f.amount) == Decimal("133.20")
