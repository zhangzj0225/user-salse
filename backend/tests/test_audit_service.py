"""Tests for AuditService."""

from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService


class TestAuditService:
    def test_log_creates_entry(self, db_session):
        entry = AuditService.log(
            action="test_action",
            operator_type="system",
            target_type="test_target",
            target_id=1,
            old_value={"before": "x"},
            new_value={"after": "y"},
            business_id="audit_test_001",
            db=db_session,
        )
        db_session.commit()

        assert entry.id is not None
        assert entry.action == "test_action"
        assert entry.operator_type == "system"
        assert entry.target_type == "test_target"
        assert entry.target_id == 1
        assert entry.old_value == {"before": "x"}
        assert entry.new_value == {"after": "y"}
        assert entry.business_id == "audit_test_001"

    def test_log_handles_none_values(self, db_session):
        entry = AuditService.log(
            action="null_test",
            operator_type="admin",
            target_type="commission_record",
            target_id=None,
            old_value=None,
            new_value=None,
            business_id=None,
            db=db_session,
        )
        db_session.commit()

        assert entry.id is not None
        assert entry.target_id is None
        assert entry.old_value is None
        assert entry.new_value is None
        assert entry.business_id is None

    def test_log_multiple_entries(self, db_session):
        e1 = AuditService.log(
            action="action_a",
            operator_type="system",
            target_type="t1",
            target_id=1,
            old_value=None,
            new_value={"v": 1},
            business_id="multi_1",
            db=db_session,
        )
        e2 = AuditService.log(
            action="action_b",
            operator_type="admin",
            target_type="t2",
            target_id=2,
            old_value={"v": 1},
            new_value={"v": 2},
            business_id="multi_2",
            db=db_session,
        )
        db_session.commit()

        assert e1.id != e2.id
        count = db_session.query(AuditLog).count()
        assert count >= 2
