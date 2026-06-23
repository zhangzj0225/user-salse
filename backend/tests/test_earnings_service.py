"""Tests for app.services.earnings_service — 收益看板。"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.earnings_service import EarningsService


def _make_user(db, email="user@example.com", role="distributor"):
    u = User(email=email, role=role, status="active")
    db.add(u)
    db.flush()
    return u


def _make_record(db, user_id, amount, rtype, source_user_id=None, business_id=None, created_at=None):
    r = CommissionRecord(
        user_id=user_id,
        amount=Decimal(amount),
        type=rtype,
        source_user_id=source_user_id,
        business_id=business_id or f"test_{rtype}_{user_id}_{amount}",
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(r)
    db.flush()
    return r


class TestGetEarnings:
    def test_empty_earnings(self, db_session):
        """无收益记录 → 余额为 0，列表为空"""
        user = _make_user(db_session)
        service = EarningsService()
        result = service.get_earnings(user.id, db_session)

        assert result["summary"]["pending_balance"] == "0.00"
        assert result["summary"]["withdrawn_total"] == "0.00"
        assert result["summary"]["available_balance"] == "0.00"
        assert result["records"] == []
        assert result["total"] == 0

    def test_summary_calculates_balance(self, db_session):
        """汇总计算记账余额"""
        user = _make_user(db_session)
        _make_record(db_session, user.id, "100.00", "first_reward", business_id="b1")
        _make_record(db_session, user.id, "50.00", "followup_reward", business_id="b2")

        service = EarningsService()
        result = service.get_earnings(user.id, db_session)

        assert result["summary"]["pending_balance"] == "150.00"
        assert result["summary"]["available_balance"] == "150.00"

    def test_records_ordered_by_time_desc(self, db_session):
        """收益明细按时间倒序"""
        user = _make_user(db_session)
        _make_record(db_session, user.id, "100.00", "first_reward",
                     business_id="b1", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        _make_record(db_session, user.id, "200.00", "followup_reward",
                     business_id="b2", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))

        service = EarningsService()
        result = service.get_earnings(user.id, db_session)

        assert len(result["records"]) == 2
        assert result["records"][0]["business_id"] == "b2"  # 更晚的在前
        assert result["records"][1]["business_id"] == "b1"

    def test_filter_by_type(self, db_session):
        """按类型筛选"""
        user = _make_user(db_session)
        _make_record(db_session, user.id, "100.00", "first_reward", business_id="b1")
        _make_record(db_session, user.id, "200.00", "followup_reward", business_id="b2")
        _make_record(db_session, user.id, "300.00", "first_reward", business_id="b3")

        service = EarningsService()
        result = service.get_earnings(user.id, db_session, record_type="first_reward")

        assert result["total"] == 2
        assert all(r["type"] == "first_reward" for r in result["records"])

    def test_invalid_filter_type(self, db_session):
        """无效类型 → ValueError"""
        user = _make_user(db_session)
        service = EarningsService()
        with pytest.raises(ValueError, match="无效"):
            service.get_earnings(user.id, db_session, record_type="invalid_type")

    def test_record_fields(self, db_session):
        """验证明细包含所有必要字段"""
        source = _make_user(db_session, "source@example.com")
        user = _make_user(db_session, "earner@example.com")
        _make_record(db_session, user.id, "488.40", "first_reward",
                     source_user_id=source.id, business_id="b1")

        service = EarningsService()
        result = service.get_earnings(user.id, db_session)

        record = result["records"][0]
        assert record["amount"] == "488.40"
        assert record["type"] == "first_reward"
        assert record["source_user_id"] == source.id
        assert record["source_email"] == "source@example.com"
        assert record["business_id"] == "b1"
        assert "created_at" in record

    def test_pagination(self, db_session):
        """分页"""
        user = _make_user(db_session)
        for i in range(10):
            _make_record(db_session, user.id, "10.00", "first_reward",
                         business_id=f"b{i}")

        service = EarningsService()
        result = service.get_earnings(user.id, db_session, limit=5, offset=0)
        assert len(result["records"]) == 5
        assert result["total"] == 10

        result2 = service.get_earnings(user.id, db_session, limit=5, offset=5)
        assert len(result2["records"]) == 5

    def test_nonexistent_user(self, db_session):
        service = EarningsService()
        with pytest.raises(ValueError, match="不存在"):
            service.get_earnings(9999, db_session)

    def test_summary_not_affected_by_filter(self, db_session):
        """汇总不受筛选影响 — 始终显示全部余额"""
        user = _make_user(db_session)
        _make_record(db_session, user.id, "100.00", "first_reward", business_id="b1")
        _make_record(db_session, user.id, "200.00", "followup_reward", business_id="b2")

        service = EarningsService()
        result = service.get_earnings(user.id, db_session, record_type="first_reward")

        # 筛选只影响 records，不影响 summary
        assert result["summary"]["pending_balance"] == "300.00"
        assert result["total"] == 1  # 只有 first_reward
