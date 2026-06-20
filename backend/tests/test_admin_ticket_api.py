"""Tests for admin ticket management (Story 3.13)。"""

import pytest
from decimal import Decimal

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.ticket import Ticket
from app.models.user import User


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.commit()
    return admin


def _make_user_with_ticket(db, email="user@example.com", amount="200.00"):
    user = User(email=email, role="user", status="active")
    db.add(user)
    db.commit()
    # 给用户佣金余额
    r = CommissionRecord(
        user_id=user.id, amount=Decimal("500.00"), type="first_reward",
        business_id=f"test_{email}",
    )
    db.add(r)
    # 创建 pending 工单
    ticket = Ticket(
        user_id=user.id, amount=Decimal(amount), payment_method="支付宝:xxx",
        status="pending",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return user, ticket


class TestListTicketsAPI:
    def test_requires_admin_auth(self, client):
        resp = client.get("/api/v1/admin/tickets")
        assert resp.status_code == 401

    def test_requires_admin_role(self, client, db_session):
        """普通用户 token 不能访问"""
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/admin/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_list_empty(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tickets"] == []
        assert resp.json()["total"] == 0

    def test_list_with_tickets(self, client, db_session):
        admin = _make_admin(db_session)
        _make_user_with_ticket(db_session, "u1@example.com", "100.00")
        _make_user_with_ticket(db_session, "u2@example.com", "200.00")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        # 验证包含 user_email
        assert data["tickets"][0]["user_email"] in ("u1@example.com", "u2@example.com")

    def test_filter_by_status(self, client, db_session):
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "100.00")
        # 创建一个 paid 工单
        t2 = Ticket(user_id=user.id, amount=Decimal("50"), payment_method="m", status="paid")
        db_session.add(t2)
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/tickets?status=pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["tickets"][0]["status"] == "pending"

    def test_invalid_status(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/tickets?status=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestApproveTicketAPI:
    def test_approve_success(self, client, db_session):
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "100.00")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/tickets/{ticket.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["processed_by"] == admin.id
        assert data["processed_at"] is not None

    def test_approve_nonexistent(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            "/api/v1/admin/tickets/99999/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_approve_already_processed(self, client, db_session):
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "100.00")
        ticket.status = "paid"
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/tickets/{ticket.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "已处理" in resp.json()["detail"]


class TestRejectTicketAPI:
    def test_reject_success(self, client, db_session):
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "100.00")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/tickets/{ticket.id}/reject",
            json={"reject_reason": "信息有误"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["reject_reason"] == "信息有误"
        assert data["processed_by"] == admin.id

    def test_reject_nonexistent(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            "/api/v1/admin/tickets/99999/reject",
            json={"reject_reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_reject_missing_reason(self, client, db_session):
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "100.00")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/tickets/{ticket.id}/reject",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422  # Pydantic validation error

    def test_reject_frees_balance(self, client, db_session):
        """拒绝后金额解冻，用户可再次提现"""
        admin = _make_admin(db_session)
        user, ticket = _make_user_with_ticket(db_session, "u1@example.com", "300.00")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        # 拒绝工单
        client.post(
            f"/api/v1/admin/tickets/{ticket.id}/reject",
            json={"reject_reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # 用户可再次创建工单（300 已解冻）
        user_token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "300.00", "payment_method": "支付宝:yyy"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
