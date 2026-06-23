"""Tests for CommissionEngine and record_commission."""

from decimal import Decimal

import pytest

from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.payment import Payment
from app.models.referral_code import ReferralCode
from app.models.user import User
from app.services.commission_service import CommissionEngine, record_commission


def _seed_commission_configs(db):
    """Seed the 9 commission configs matching PRD v2."""
    configs = [
        ("agent", "first_reward_888", "fixed", 488.40),
        ("agent", "first_reward_5000", "fixed", 2750.00),
        ("agent", "first_reward_10000", "fixed", 5500.00),
        ("agent", "followup_reward", "fixed", 133.20),
        ("agent", "team_bonus", "percentage", 0.05),
        ("distributor", "first_reward_888", "fixed", 355.20),
        ("distributor", "first_reward_5000", "fixed", 2000.00),
        ("distributor", "first_reward_10000", "fixed", 4000.00),
        ("distributor", "team_bonus", "percentage", 0.04),
    ]
    for role, scene, rtype, rval in configs:
        db.add(CommissionConfig(role=role, scene=scene, reward_type=rtype, reward_value=rval))
    db.flush()


def _make_user(db, email, role="distributor", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


def _make_referral_code(db, user_id):
    from app.core.security import generate_invite_code
    code = generate_invite_code(user_id)
    rc = ReferralCode(code=code, user_id=user_id, key_version=1)
    db.add(rc)
    db.flush()
    return rc


class TestRecordCommission:
    def test_creates_record_and_returns_it(self, db_session):
        result = record_commission(
            user_id=1, amount=100.00, commission_type="first_reward",
            source_user_id=2, business_id="test_biz_001", db=db_session,
        )
        db_session.commit()
        assert result is not None
        assert result.id is not None
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


class TestGetConfig:
    def test_returns_config_when_exists(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)
        config = engine.get_config(role="agent", scene="first_reward_888")
        assert config is not None
        assert config.reward_type == "fixed"
        assert float(config.reward_value) == 488.40

    def test_returns_none_when_not_exists(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)
        config = engine.get_config(role="agent", scene="nonexistent_scene")
        assert config is None


class TestCalculateFirstReward:
    def test_agent_payment_888(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        engine = CommissionEngine(db_session)
        result = engine.calculate_first_reward(
            referrer_user_id=agent.id, payment_amount=888, payment_id=1
        )
        assert result is not None
        assert result["amount"] == Decimal("488.40")
        assert result["business_id"] == "payment_1"

    def test_agent_payment_5000(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        engine = CommissionEngine(db_session)
        result = engine.calculate_first_reward(
            referrer_user_id=agent.id, payment_amount=5000, payment_id=2
        )
        assert result is not None
        assert result["amount"] == 2750.00

    def test_distributor_payment_888(self, db_session):
        _seed_commission_configs(db_session)
        dist = _make_user(db_session, "dist@test.com", role="distributor")
        engine = CommissionEngine(db_session)
        result = engine.calculate_first_reward(
            referrer_user_id=dist.id, payment_amount=888, payment_id=4
        )
        assert result is not None
        assert result["amount"] == Decimal("355.20")

    def test_nonexistent_parent_returns_none(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)
        result = engine.calculate_first_reward(
            referrer_user_id=9999, payment_amount=888, payment_id=12
        )
        assert result is None


class TestCalculateFollowupReward:
    def test_agent_distributor_chain_returns_133_2(self, db_session):
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        distributor = _make_user(db_session, "dist@test.com", role="distributor", parent_id=agent.id)
        engine = CommissionEngine(db_session)
        result = engine.calculate_followup_reward(
            payment_id=42, referrer_user_id=distributor.id
        )
        assert result is not None
        assert result["amount"] == Decimal("133.20")
        assert result["business_id"] == "payment_42_followup_" + str(agent.id)

    def test_grandparent_not_agent_returns_none(self, db_session):
        _seed_commission_configs(db_session)
        dist1 = _make_user(db_session, "dist1@test.com", role="distributor")
        dist2 = _make_user(db_session, "dist2@test.com", role="distributor", parent_id=dist1.id)
        engine = CommissionEngine(db_session)
        result = engine.calculate_followup_reward(
            payment_id=42, referrer_user_id=dist2.id
        )
        assert result is None

    def test_no_grandparent_returns_none(self, db_session):
        _seed_commission_configs(db_session)
        distributor = _make_user(db_session, "dist@test.com", role="distributor")
        engine = CommissionEngine(db_session)
        result = engine.calculate_followup_reward(
            payment_id=42, referrer_user_id=distributor.id
        )
        assert result is None


class TestProcessPayment:
    def test_records_first_reward_for_agent_parent(self, db_session):
        """代理的上级（也是代理）通过推荐码支付 888 → 首次奖励 488.40"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        rc = _make_referral_code(db_session, parent.id)

        payment = Payment(
            email="child@test.com", amount=888, target_role="member_license",
            status="pending", referral_code=rc.code,
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=payment.id)
        db_session.commit()

        assert len(records) == 1
        assert records[0].user_id == parent.id
        assert float(records[0].amount) == 488.40
        assert records[0].business_id == f"payment_{payment.id}"

    def test_no_referral_code_returns_empty(self, db_session):
        """无推荐码 = 不产生佣金"""
        _seed_commission_configs(db_session)
        payment = Payment(
            email="loner@test.com", amount=888, target_role="member_license",
            status="pending",
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=payment.id)
        assert records == []

    def test_nonexistent_payment_returns_empty(self, db_session):
        _seed_commission_configs(db_session)
        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=9999)
        assert records == []

    def test_idempotent_same_payment(self, db_session):
        """同一笔支付重复调用，不产生重复记录"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        rc = _make_referral_code(db_session, parent.id)

        payment = Payment(
            email="child@test.com", amount=888, target_role="member_license",
            status="pending", referral_code=rc.code,
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records1 = engine.process_payment(payment_id=payment.id)
        db_session.commit()
        records2 = engine.process_payment(payment_id=payment.id)
        db_session.commit()

        assert len(records1) == 1
        assert len(records2) == 0

    def test_distributor_parent_gets_first_reward(self, db_session):
        """经销商的上级通过推荐码支付 888 → 首次奖励 355.20"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="distributor")
        rc = _make_referral_code(db_session, parent.id)

        payment = Payment(
            email="child@test.com", amount=888, target_role="member_license",
            status="pending", referral_code=rc.code,
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=payment.id)
        db_session.commit()

        assert len(records) == 1
        assert float(records[0].amount) == 355.20

    def test_followup_triggered_on_distributor_subordinate(self, db_session):
        """C(用户)通过推荐码支付888，推荐人B是经销商，B上级A是代理 → A获后续收益 133.2"""
        _seed_commission_configs(db_session)
        agent = _make_user(db_session, "agent@test.com", role="agent")
        distributor = _make_user(db_session, "dist@test.com", role="distributor", parent_id=agent.id)
        rc = _make_referral_code(db_session, distributor.id)

        payment = Payment(
            email="c@test.com", amount=888, target_role="member_license",
            status="pending", referral_code=rc.code,
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=payment.id)
        db_session.commit()

        # 两条：首次奖励(给经销商B 355.20) + 后续收益(给代理A 133.20)
        assert len(records) == 2
        by_type = {r.type: r for r in records}
        assert by_type["first_reward"].user_id == distributor.id
        assert Decimal(by_type["first_reward"].amount) == Decimal("355.20")
        assert by_type["followup_reward"].user_id == agent.id
        assert Decimal(by_type["followup_reward"].amount) == Decimal("133.20")

    def test_invalid_amount_returns_empty(self, db_session):
        """SF-1: 非法金额跳过佣金记账"""
        _seed_commission_configs(db_session)
        parent = _make_user(db_session, "parent@test.com", role="agent")
        rc = _make_referral_code(db_session, parent.id)

        payment = Payment(
            email="child@test.com", amount=999, target_role="member_license",
            status="pending", referral_code=rc.code,
        )
        db_session.add(payment)
        db_session.flush()

        engine = CommissionEngine(db_session)
        records = engine.process_payment(payment_id=payment.id)
        assert records == []


class TestRecordCommissionConcurrency:
    def test_duplicate_flush_returns_none_not_raise(self, db_session):
        db_session.add(CommissionRecord(
            user_id=1, amount=Decimal("100.00"), type="first_reward",
            source_user_id=2, business_id="race_biz_001",
        ))
        db_session.commit()

        result = record_commission(
            user_id=1, amount=Decimal("200.00"), commission_type="first_reward",
            source_user_id=3, business_id="race_biz_001", db=db_session,
        )
        assert result is None
