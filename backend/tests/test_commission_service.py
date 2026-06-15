"""Tests for CommissionEngine and record_commission."""

import pytest

from app.models.commission_record import CommissionRecord
from app.services.commission_service import CommissionEngine, record_commission


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
        # First call creates
        result1 = record_commission(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=2,
            business_id="test_biz_002",
            db=db_session,
        )
        db_session.commit()

        # Second call with same business_id returns None
        result2 = record_commission(
            user_id=1,
            amount=200.00,  # Different amount — should be ignored
            commission_type="sale_commission",
            source_user_id=3,
            business_id="test_biz_002",  # Same business_id
            db=db_session,
        )

        assert result1 is not None
        assert result2 is None

        # Only one record exists
        count = (
            db_session.query(CommissionRecord)
            .filter(CommissionRecord.business_id == "test_biz_002")
            .count()
        )
        assert count == 1

    def test_different_business_ids_create_separate_records(self, db_session):
        result1 = record_commission(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=None,
            business_id="biz_a",
            db=db_session,
        )
        result2 = record_commission(
            user_id=1,
            amount=200.00,
            commission_type="sale_commission",
            source_user_id=None,
            business_id="biz_b",
            db=db_session,
        )
        db_session.commit()

        assert result1 is not None
        assert result2 is not None
        assert result1.id != result2.id
        assert result1.business_id == "biz_a"
        assert result2.business_id == "biz_b"

    def test_handles_none_source_user_id(self, db_session):
        result = record_commission(
            user_id=1,
            amount=50.00,
            commission_type="recommend",
            source_user_id=None,
            business_id="biz_none_source",
            db=db_session,
        )
        db_session.commit()

        assert result is not None
        assert result.source_user_id is None

    def test_writes_audit_log(self, db_session):
        from app.models.audit_log import AuditLog

        result = record_commission(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=2,
            business_id="biz_audit_test",
            db=db_session,
        )
        db_session.commit()

        # Verify audit log was created
        audit_entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.business_id == "biz_audit_test")
            .first()
        )
        assert audit_entry is not None
        assert audit_entry.action == "commission_create"
        assert audit_entry.operator_type == "system"
        assert audit_entry.target_type == "commission_record"
        assert audit_entry.target_id == result.id


class TestCommissionEngine:
    def test_init_stores_db_session(self, db_session):
        engine = CommissionEngine(db_session)
        assert engine.db is db_session

    def test_calculate_raises_not_implemented(self, db_session):
        engine = CommissionEngine(db_session)
        with pytest.raises(NotImplementedError):
            engine.calculate(user_id=1, scene="self_sell")

    def test_record_delegates_to_record_commission(self, db_session):
        engine = CommissionEngine(db_session)
        result = engine.record(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=2,
            business_id="engine_test_001",
        )
        db_session.commit()

        assert result is not None
        assert result.business_id == "engine_test_001"

    def test_record_is_idempotent(self, db_session):
        engine = CommissionEngine(db_session)
        result1 = engine.record(
            user_id=1,
            amount=100.00,
            commission_type="first_reward",
            source_user_id=None,
            business_id="engine_idempotent",
        )
        db_session.commit()

        result2 = engine.record(
            user_id=1,
            amount=999.00,
            commission_type="sale_commission",
            source_user_id=None,
            business_id="engine_idempotent",
        )

        assert result1 is not None
        assert result2 is None

    def test_log_audit_writes_entry(self, db_session):
        from app.models.audit_log import AuditLog

        engine = CommissionEngine(db_session)
        engine.log_audit(
            action="test_action",
            target_type="test_target",
            target_id=42,
            old_value={"before": "x"},
            new_value={"after": "y"},
            business_id="log_audit_test",
        )
        db_session.commit()

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.business_id == "log_audit_test")
            .first()
        )
        assert entry is not None
        assert entry.action == "test_action"
        assert entry.target_type == "test_target"
        assert entry.target_id == 42
        assert entry.old_value == {"before": "x"}
        assert entry.new_value == {"after": "y"}
