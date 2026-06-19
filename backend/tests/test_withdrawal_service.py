"""Tests for app.services.withdrawal_service — 提现工单。"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.commission_record import CommissionRecord
from app.models.ticket import Ticket
from app.models.user import User
from app.services.withdrawal_service import WithdrawalService


def _make_user(db, email="user@example.com"):
    u = User(email=email, role="user", status="active")
    db.add(u)
    db.flush()
    return u


def _add_commission(db, user_id, amount, business_id=None):
    r = CommissionRecord(
        user_id=user_id,
        amount=Decimal(amount),
        type="first_reward",
        business_id=business_id or f"test_{user_id}_{amount}",
    )
    db.add(r)
    db.flush()
    return r


class TestCreateTicket:
    def test_create_success(self, db_session):
        """正常创建提现工单"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        result = service.create_ticket(user.id, "200.00", "支付宝:xxx", db_session)

        assert result["ticket_id"] is not None
        assert result["amount"] == "200.00"
        assert result["status"] == "pending"
        # 500 - 200 = 300 可用
        assert result["available_balance"] == "300.00"

        ticket = db_session.query(Ticket).first()
        assert ticket.amount == Decimal("200.00")
        assert ticket.status == "pending"
        assert ticket.payment_method == "支付宝:xxx"

    def test_below_minimum_amount(self, db_session):
        """低于最低提现额 → 失败"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        with pytest.raises(ValueError, match="最低提现额"):
            service.create_ticket(user.id, "50.00", "支付宝:xxx", db_session)

    def test_exceeds_available_balance(self, db_session):
        """超过可用余额 → 失败"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "100.00", "b1")

        service = WithdrawalService()
        with pytest.raises(ValueError, match="超过可用余额"):
            service.create_ticket(user.id, "200.00", "支付宝:xxx", db_session)

    def test_zero_amount(self, db_session):
        """金额为 0 → 失败"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        with pytest.raises(ValueError, match="大于 0"):
            service.create_ticket(user.id, "0", "支付宝:xxx", db_session)

    def test_negative_amount(self, db_session):
        """负数金额 → 失败"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        with pytest.raises(ValueError, match="大于 0"):
            service.create_ticket(user.id, "-100", "支付宝:xxx", db_session)

    def test_invalid_amount_format(self, db_session):
        """非法金额格式 → 失败"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        with pytest.raises(ValueError, match="格式无效"):
            service.create_ticket(user.id, "abc", "支付宝:xxx", db_session)

    def test_no_balance(self, db_session):
        """无收益余额 → 失败"""
        user = _make_user(db_session)
        service = WithdrawalService()
        with pytest.raises(ValueError, match="超过可用余额"):
            service.create_ticket(user.id, "100.00", "支付宝:xxx", db_session)

    def test_freeze_reduces_available(self, db_session):
        """创建工单后可用余额减少"""
        user = _make_user(db_session)
        _add_commission(db_session, user.id, "500.00", "b1")

        service = WithdrawalService()
        service.create_ticket(user.id, "200.00", "支付宝:xxx", db_session)

        # 再次提现，可用余额 = 500 - 200 = 300
        result = service.create_ticket(user.id, "100.00", "支付宝:yyy", db_session)
        assert result["available_balance"] == "200.00"

    def test_nonexistent_user(self, db_session):
        service = WithdrawalService()
        with pytest.raises(ValueError, match="不存在"):
            service.create_ticket(9999, "100.00", "支付宝:xxx", db_session)


class TestListUserTickets:
    def test_empty_list(self, db_session):
        """无工单 → 空列表"""
        user = _make_user(db_session)
        service = WithdrawalService()
        tickets = service.list_user_tickets(user.id, db_session)
        assert tickets == []

    def test_list_all(self, db_session):
        """列出所有工单"""
        user = _make_user(db_session)
        t1 = Ticket(user_id=user.id, amount=Decimal("100"), payment_method="m1", status="pending")
        t2 = Ticket(user_id=user.id, amount=Decimal("200"), payment_method="m2", status="paid")
        db_session.add_all([t1, t2])
        db_session.flush()

        service = WithdrawalService()
        tickets = service.list_user_tickets(user.id, db_session)
        assert len(tickets) == 2

    def test_filter_by_status(self, db_session):
        """按状态筛选"""
        user = _make_user(db_session)
        t1 = Ticket(user_id=user.id, amount=Decimal("100"), payment_method="m1", status="pending")
        t2 = Ticket(user_id=user.id, amount=Decimal("200"), payment_method="m2", status="paid")
        t3 = Ticket(user_id=user.id, amount=Decimal("300"), payment_method="m3", status="pending")
        db_session.add_all([t1, t2, t3])
        db_session.flush()

        service = WithdrawalService()
        tickets = service.list_user_tickets(user.id, db_session, status="pending")
        assert len(tickets) == 2
        assert all(t["status"] == "pending" for t in tickets)

    def test_invalid_status(self, db_session):
        """无效状态 → 失败"""
        user = _make_user(db_session)
        service = WithdrawalService()
        with pytest.raises(ValueError, match="无效"):
            service.list_user_tickets(user.id, db_session, status="invalid")

    def test_ordered_by_time_desc(self, db_session):
        """按时间倒序"""
        user = _make_user(db_session)
        t1 = Ticket(user_id=user.id, amount=Decimal("100"), payment_method="m1",
                    status="pending", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        t2 = Ticket(user_id=user.id, amount=Decimal("200"), payment_method="m2",
                    status="pending", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
        db_session.add_all([t1, t2])
        db_session.flush()

        service = WithdrawalService()
        tickets = service.list_user_tickets(user.id, db_session)
        assert tickets[0]["amount"] == "200"
        assert tickets[1]["amount"] == "100"
