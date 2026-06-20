"""Tests for Story 5.1 long-term reward settlement."""

from decimal import Decimal

from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.commission_service import CommissionEngine, record_commission


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


def _add_commission(db, user_id, amount, business_id):
    record = CommissionRecord(
        user_id=user_id, amount=Decimal(str(amount)),
        type="first_reward", business_id=business_id,
    )
    db.add(record)
    db.flush()
    return record


class TestCalculateLongTermReward:
    """Long-term reward calculation tests."""

    def test_agent_gets_5_percent(self, db_session, seed_commission_configs):
        """Agent gets 5% of direct subordinates' total commission."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child1 = _make_user(db_session, "c1@example.com", "member", parent_id=agent.id)
        child2 = _make_user(db_session, "c2@example.com", "member", parent_id=agent.id)
        _add_commission(db_session, child1.id, 1000, "t1")
        _add_commission(db_session, child2.id, 2000, "t2")
        db_session.commit()

        engine = CommissionEngine(db_session)
        # period 202607 -> previous month = June 2026 (current month when records created)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        db_session.commit()

        assert len(records) == 1
        # (1000 + 2000) * 0.05 = 150.00
        assert records[0].amount == Decimal("150.00")
        assert records[0].type == "team_bonus"
        assert records[0].business_id == "settle_{}_202607".format(agent.id)

    def test_distributor_gets_4_percent(self, db_session, seed_commission_configs):
        """Distributor gets 4% of direct subordinates' total commission."""
        dist = _make_user(db_session, "dist@example.com", "distributor")
        child1 = _make_user(db_session, "c1@example.com", "member", parent_id=dist.id)
        _add_commission(db_session, child1.id, 1000, "t1")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(dist.id, "202607", db=db_session)
        db_session.commit()

        assert len(records) == 1
        # 1000 * 0.04 = 40.00
        assert records[0].amount == Decimal("40.00")

    def test_agent_excludes_distributor_children(self, db_session, seed_commission_configs):
        """Agent's distributor children excluded (covered by followup_reward)."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        member_child = _make_user(db_session, "member@example.com", "member", parent_id=agent.id)
        dist_child = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        _add_commission(db_session, member_child.id, 1000, "t1")
        _add_commission(db_session, dist_child.id, 5000, "t2")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        db_session.commit()

        assert len(records) == 1
        # Only member_child's 1000 * 0.05 = 50.00 (dist_child excluded)
        assert records[0].amount == Decimal("50.00")

    def test_distributor_includes_all_children(self, db_session, seed_commission_configs):
        """Distributor includes all children."""
        dist = _make_user(db_session, "dist@example.com", "distributor")
        member_child = _make_user(db_session, "member@example.com", "member", parent_id=dist.id)
        dist_child = _make_user(db_session, "dist2@example.com", "distributor", parent_id=dist.id)
        _add_commission(db_session, member_child.id, 1000, "t1")
        _add_commission(db_session, dist_child.id, 2000, "t2")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(dist.id, "202607", db=db_session)
        db_session.commit()

        assert len(records) == 1
        # (1000 + 2000) * 0.04 = 120.00
        assert records[0].amount == Decimal("120.00")

    def test_idempotent(self, db_session, seed_commission_configs):
        """Same period not settled twice."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "c@example.com", "member", parent_id=agent.id)
        _add_commission(db_session, child.id, 1000, "t1")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records1 = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        db_session.commit()

        records2 = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        db_session.commit()

        assert len(records1) == 1
        assert len(records2) == 0  # idempotent

    def test_no_children(self, db_session, seed_commission_configs):
        """No children = no settlement."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        assert records == []

    def test_no_child_income(self, db_session, seed_commission_configs):
        """Children with no commission = no settlement."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "c@example.com", "member", parent_id=agent.id)
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        assert records == []

    def test_regular_user_no_reward(self, db_session, seed_commission_configs):
        """Regular users get no long-term reward."""
        user = _make_user(db_session, "user@example.com", "user")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(user.id, "202607", db=db_session)
        assert records == []

    def test_member_no_reward(self, db_session, seed_commission_configs):
        """Members get no long-term reward."""
        member = _make_user(db_session, "member@example.com", "member")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(member.id, "202607", db=db_session)
        assert records == []

    def test_nonexistent_user(self, db_session, seed_commission_configs):
        """Nonexistent user returns empty."""
        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(99999, "202607", db=db_session)
        assert records == []

    def test_agent_all_distributor_children_excluded(self, db_session, seed_commission_configs):
        """Agent with only distributor children = no settlement."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        dist1 = _make_user(db_session, "d1@example.com", "distributor", parent_id=agent.id)
        dist2 = _make_user(db_session, "d2@example.com", "distributor", parent_id=agent.id)
        _add_commission(db_session, dist1.id, 5000, "t1")
        _add_commission(db_session, dist2.id, 3000, "t2")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        assert records == []

    def test_previous_period_excluded(self, db_session, seed_commission_configs):
        """Commissions from outside the previous period are not counted."""
        from datetime import datetime, timezone, timedelta
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "c@example.com", "member", parent_id=agent.id)
        # Create commission record dated 3 months ago (outside previous period)
        old_date = datetime.now(timezone.utc) - timedelta(days=90)
        record = CommissionRecord(
            user_id=child.id, amount=Decimal("10000"),
            type="first_reward", business_id="old_t1",
            created_at=old_date,
        )
        db_session.add(record)
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        # Old commission should not be counted -> no reward
        assert records == []


class TestSchedulerService:
    """Scheduler service tests."""

    def test_run_settlement_logic(self, db_session, seed_commission_configs):
        """Verify settlement logic (directly via engine, not scheduler session)."""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "c@example.com", "member", parent_id=agent.id)
        _add_commission(db_session, child.id, 1000, "t1")
        db_session.commit()

        engine = CommissionEngine(db_session)
        records = engine.calculate_long_term_reward(agent.id, "202607", db=db_session)
        db_session.commit()

        assert len(records) == 1
        assert records[0].amount == Decimal("50.00")
        assert records[0].type == "team_bonus"
