"""Tests for CommissionEngine and record_commission."""

import pytest

from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.commission_service import CommissionEngine, record_commission


# ── Helpers ──────────────────────────────────────────────

def _seed_commission_configs(db):
    """Seed the 11 commission configs matching migration 004."""
    configs = [
        ("agent", "recharge_888", "fixed", 488.40),
        ("agent", "recharge_5000", "fixed", 2750.00),
        ("agent", "recharge_10000", "fixed", 5500.00),
        ("agent", "followup_reward", "fixed", 133.20),
        ("agent", "team_bonus", "percentage", 0.05),
        ("distributor", "recharge_888", "fixed", 355.20),
        ("distributor", "recharge_5000", "fixed", 2000.00),
        ("distributor", "recharge_10000", "fixed", 4000.00),
        ("distributor", "team_bonus", "percentage", 0.04),
        ("member", "recharge_888", "fixed", 177.60),
        ("user", "recharge_888", "fixed", 177.60),
    ]
    for role, scene, rtype, rval in configs:
        db.add(CommissionConfig(role=role, scene=scene, reward_type=rtype, reward_value=rval))
    db.flush()


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


# ── Existing tests (unchanged) ───────────────────────────

class TestRecordCommission:
    def test_creates_record_and_returns_it(self, db_session):
        result = record_commission(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=2,
            business_id="test_biz_001",
            db=db_session,
        )
        db_session.commit()

        assert result is not None
        assert result.id is not None
        assert result.user_id == 1
        assert result.amount == 100.00
        assert result.type == "first_reward"
        assert result.source_user_id == 2
        assert result.business_id == "test_biz_001"

    def test_idempotent_same_business_id_returns_none(self, db_session):
        result1 = record_commission(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=2, business_id="test_biz_002", db=db_session,
        )
        db_session.commit()

        result2 = record_commission(
            user_id=1, amount=200.00, commission_type="sale_commission",
            source_user_id=3, business_id="test_biz_002", db=db_session,
        )

        assert result1 is not None
        assert result2 is None
        count = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == "test_biz_002"
        ).count()
        assert count == 1

    def test_different_business_ids_create_separate_records(self, db_session):
        result1 = record_commission(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=None, business_id="biz_a", db=db_session,
        )
        result2 = record_commission(
            user_id=1, amount=200.00, commission_type="sale_commission",
            source_user_id=None, business_id="biz_b", db=db_session,
        )
        db_session.commit()

        assert result1 is not None
        assert result2 is not None
        assert result1.id != result2.id

    def test_handles_none_source_user_id(self, db_session):
        result = record_commission(
            user_id=1, amount=50.00, commission_type="recommend",
            source_user_id=None, business_id="biz_none_source", db=db_session,
        )
        db_session.commit()
        assert result is not None
        assert result.source_user_id is None

    def test_writes_audit_log(self, db_session):
        from app.models.audit_log import AuditLog

        result = record_commission(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=2, business_id="biz_audit_test", db=db_session,
        )
        db_session.commit()

        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.business_id == "biz_audit_test"
        ).first()
        assert audit_entry is not None
        assert audit_entry.action == "commission_create"


class TestCommissionEngine:
    def test_init_stores_db_session(self, db_session):
        engine = CommissionEngine(db_session)
        assert engine.db is db_session

    def test_record_delegates_to_record_commission(self, db_session):
        engine = CommissionEngine(db_session)
        result = engine.record(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=2, business_id="engine_test_001",
        )
        db_session.commit()
        assert result is not None
        assert result.business_id == "engine_test_001"

    def test_record_is_idempotent(self, db_session):
        engine = CommissionEngine(db_session)
        result1 = engine.record(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=None, business_id="engine_idempotent",
        )
        db_session.commit()
        result2 = engine.record(
            user_id=1, amount=999.00, commission_type="sale_commission",
            source_user_id=None, business_id="engine_idempotent",
        )
        assert result1 is not None
        assert result2 is None

    def test_log_audit_writes_entry(self, db_session):
        from app.models.audit_log import AuditLog

        engine = CommissionEngine(db_session)
        engine.log_audit(
            action="test_action", target_type="test_target", target_id=42,
            old_value={"before": "x"}, new_value={"after": "y"},
            business_id="log_audit_test",
        )
        db_session.commit()
        entry = db_session.query(AuditLog).filter(
            AuditLog.business_id == "log_audit_test"
        ).first()
        assert entry is not None
        assert entry.action == "test_action"


# ── AC4: get_config ──────────────────────────────────────

class TestGetConfig:
    def test_returns_config_when_exists(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        config = engine.get_config(role="agent", scene="recharge_888")
        assert config is not None
        assert config.reward_type == "fixed"
        assert float(config.reward_value) == 488.40

    def test_returns_none_when_not_exists(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        # 普通用户充 5000 无配置
        config = engine.get_config(role="user", scene="recharge_5000")
        assert config is None

    def test_returns_none_for_nonexistent_role(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        config = engine.get_config(role="agent", scene="nonexistent_scene")
        assert config is None


# ── AC1: calculate_first_reward ──────────────────────────

class TestCalculateFirstReward:
    def test_agent_recharge_888(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=agent.id, recharge_amount=888, recharge_id=1
        )
        assert result is not None
        assert result["user_id"] == agent.id
        assert result["amount"] == 488.40
        assert result["commission_type"] == "first_reward"
        assert result["business_id"] == "recharge_1"
        assert result["source_user_id"] is None

    def test_agent_recharge_5000(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=agent.id, recharge_amount=5000, recharge_id=2
        )
        assert result is not None
        assert result["amount"] == 2750.00
        assert result["business_id"] == "recharge_2"

    def test_agent_recharge_10000(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=agent.id, recharge_amount=10000, recharge_id=3
        )
        assert result is not None
        assert result["amount"] == 5500.00

    def test_distributor_recharge_888(self, db_session):
        _seed_commission_configs(db_session)
        dist = _make_user(db_session, "dist@test.com", role="distributor")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=dist.id, recharge_amount=888, recharge_id=4
        )
        assert result is not None
        assert result["amount"] == 355.20

    def test_distributor_recharge_5000(self, db_session):
        _seed_commission_configs(db_session)
        dist = _make_user(db_session, "dist@test.com", role="distributor")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=dist.id, recharge_amount=5000, recharge_id=5
        )
        assert result is not None
        assert result["amount"] == 2000.00

    def test_distributor_recharge_10000(self, db_session):
        _seed_commission_configs(db_session)
        dist = _make_user(db_session, "dist@test.com", role="distributor")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=dist.id, recharge_amount=10000, recharge_id=6
        )
        assert result is not None
        assert result["amount"] == 4000.00

    def test_member_recharge_888(self, db_session):
        _seed_commission_configs(db_session)
        member = _make_user(db_session, "member@test.com", role="member")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=member.id, recharge_amount=888, recharge_id=7
        )
        assert result is not None
        assert result["amount"] == 177.60

    def test_user_recharge_888(self, db_session):
        _seed_commission_configs(db_session)
        user = _make_user(db_session, "user@test.com", role="user")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=user.id, recharge_amount=888, recharge_id=8
        )
        assert result is not None
        assert result["amount"] == 177.60

    def test_user_recharge_5000_returns_none(self, db_session):
        """普通用户推荐的人充 5000 不产生佣金"""
        _seed_commission_configs(db_session)
        user = _make_user(db_session, "user@test.com", role="user")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=user.id, recharge_amount=5000, recharge_id=9
        )
        assert result is None

    def test_user_recharge_10000_returns_none(self, db_session):
        """普通用户推荐的人充 10000 不产生佣金"""
        _seed_commission_configs(db_session)
        user = _make_user(db_session, "user@test.com", role="user")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=user.id, recharge_amount=10000, recharge_id=10
        )
        assert result is None

    def test_member_recharge_5000_returns_none(self, db_session):
        """888会员推荐的人充 5000 不产生佣金"""
        _seed_commission_configs(db_session)
        member = _make_user(db_session, "member@test.com", role="member")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=member.id, recharge_amount=5000, recharge_id=11
        )
        assert result is None

    def test_member_recharge_10000_returns_none(self, db_session):
        """888会员推荐的人充 10000 不产生佣金"""
        _seed_commission_configs(db_session)
        member = _make_user(db_session, "member@test.com", role="member")
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=member.id, recharge_amount=10000, recharge_id=13
        )
        assert result is None

    def test_nonexistent_parent_returns_none(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        result = engine.calculate_first_reward(
            parent_user_id=9999, recharge_amount=888, recharge_id=12
        )
        assert result is None


# ── AC2: calculate_followup_reward ───────────────────────

class TestCalculateFollowupReward:
    def test_agent_distributor_returns_133_2(self, db_session):
        """代理→经销商关系，经销商的下级充 888，代理获 133.2 元"""
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        distributor = _make_user(db_session, "dist@test.com", role="distributor", parent_id=agent.id)
        engine = CommissionEngine(db_session)

        result = engine.calculate_followup_reward(
            agent_id=agent.id, distributor_id=distributor.id, recharge_id=42
        )
        assert result is not None
        assert result["amount"] == 133.20
        assert result["commission_type"] == "followup_reward"
        assert result["business_id"] == "recharge_42_followup_" + str(agent.id)
        assert result["source_user_id"] == distributor.id

    def test_non_agent_returns_none(self, db_session):
        """上级不是代理，不产生后续收益"""
        _seed_commission_configs(db_session)
        dist1 = _make_user(db_session, "dist1@test.com", role="distributor")
        dist2 = _make_user(db_session, "dist2@test.com", role="distributor", parent_id=dist1.id)
        engine = CommissionEngine(db_session)

        result = engine.calculate_followup_reward(
            agent_id=dist1.id, distributor_id=dist2.id, recharge_id=42
        )
        assert result is None

    def test_non_distributor_returns_none(self, db_session):
        """直接上级不是经销商，不产生后续收益"""
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        member = _make_user(db_session, "member@test.com", role="member", parent_id=agent.id)
        engine = CommissionEngine(db_session)

        result = engine.calculate_followup_reward(
            agent_id=agent.id, distributor_id=member.id, recharge_id=42
        )
        assert result is None

    def test_nonexistent_users_return_none(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        result = engine.calculate_followup_reward(
            agent_id=9999, distributor_id=9998, recharge_id=42
        )
        assert result is None


# ── AC3: calculate_long_term_reward ──────────────────────

class TestCalculateLongTermReward:
    def test_raises_not_implemented(self, db_session):
        engine = CommissionEngine(db_session)
        with pytest.raises(NotImplementedError):
            engine.calculate_long_term_reward(user_id=1, period="2026-06")


# ── AC7: process_recharge ────────────────────────────────

class TestProcessRecharge:
    def test_records_first_reward_for_agent_parent(self, db_session):
        """代理的上级（也是代理）充 888 → 首次奖励 488.40"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=100, recharger_user_id=child.id, amount=888
        )
        db_session.commit()

        assert len(records) == 1
        assert records[0].user_id == parent.id
        assert float(records[0].amount) == 488.40
        assert records[0].type == "first_reward"
        assert records[0].business_id == "recharge_100"
        assert records[0].source_user_id == child.id

    def test_no_parent_returns_empty(self, db_session):
        """无上级（parent_id=None），跳过所有佣金"""
        _seed_commission_configs(db_session)
        user = _make_user(db_session, "loner@test.com", role="user")
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=101, recharger_user_id=user.id, amount=888
        )
        assert records == []

    def test_no_config_returns_empty(self, db_session):
        """普通用户上级充 5000 → 无配置，跳过"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="user")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=102, recharger_user_id=child.id, amount=5000
        )
        assert records == []

    def test_nonexistent_user_returns_empty(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=103, recharger_user_id=9999, amount=888
        )
        assert records == []

    def test_idempotent_same_recharge(self, db_session):
        """同一笔充值重复调用，不产生重复记录"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records1 = engine.process_recharge(
            recharge_id=200, recharger_user_id=child.id, amount=888
        )
        db_session.commit()

        records2 = engine.process_recharge(
            recharge_id=200, recharger_user_id=child.id, amount=888
        )
        db_session.commit()

        assert len(records1) == 1
        assert len(records2) == 0  # 幂等，第二次无新记录

        count = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == "recharge_200"
        ).count()
        assert count == 1

    def test_distributor_parent_gets_first_reward(self, db_session):
        """经销商的上级充 888 → 首次奖励 355.20"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="distributor")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=201, recharger_user_id=child.id, amount=888
        )
        db_session.commit()

        assert len(records) == 1
        assert float(records[0].amount) == 355.20

    def test_user_parent_recharge_888_gets_177_60(self, db_session):
        """普通用户上级充 888 → 首次奖励 177.60"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="user")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=202, recharger_user_id=child.id, amount=888
        )
        db_session.commit()

        assert len(records) == 1
        assert float(records[0].amount) == 177.60

    def test_agent_parent_distributor_child_no_followup(self, db_session):
        """SF-6: 代理上级 + 经销商充值人 → 只有首次奖励，无后续收益"""
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        distributor = _make_user(db_session, "dist@test.com", role="distributor", parent_id=agent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=300, recharger_user_id=distributor.id, amount=888
        )
        db_session.commit()

        # 应该只有 1 条首次奖励记录（488.40），不应有 followup_reward
        assert len(records) == 1
        assert records[0].type == "first_reward"
        assert float(records[0].amount) == 488.40

        # 确认无 followup_reward 记录
        followup_count = db_session.query(CommissionRecord).filter(
            CommissionRecord.type == "followup_reward",
            CommissionRecord.business_id.like("%recharge_300%"),
        ).count()
        assert followup_count == 0

    def test_agent_parent_recharge_5000(self, db_session):
        """SF-7: 代理上级 + 充值 5000 → 首次奖励 2750.00"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=301, recharger_user_id=child.id, amount=5000
        )
        db_session.commit()

        assert len(records) == 1
        assert float(records[0].amount) == 2750.00
        assert records[0].business_id == "recharge_301"

    def test_agent_parent_recharge_10000(self, db_session):
        """SF-7: 代理上级 + 充值 10000 → 首次奖励 5500.00"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=302, recharger_user_id=child.id, amount=10000
        )
        db_session.commit()

        assert len(records) == 1
        assert float(records[0].amount) == 5500.00
        assert records[0].business_id == "recharge_302"

    def test_invalid_amount_returns_empty(self, db_session):
        """SF-1: 非法金额（如 999）跳过佣金记账"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        child = _make_user(db_session, "child@test.com", role="user", parent_id=parent.id)
        engine = CommissionEngine(db_session)

        records = engine.process_recharge(
            recharge_id=303, recharger_user_id=child.id, amount=999
        )
        assert records == []
