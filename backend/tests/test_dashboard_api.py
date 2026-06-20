"""Tests for Story 4.3 运营数据看板。"""

from decimal import Decimal

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.recharge import Recharge
from app.models.ticket import Ticket
from app.models.user import User


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.commit()
    return admin


class TestDashboardAPI:
    def test_requires_admin_auth(self, client):
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 401

    def test_requires_admin_role(self, client, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_empty_dashboard(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 0
        assert data["agent_count"] == 0
        assert data["distributor_count"] == 0
        assert data["member_count"] == 0
        assert data["regular_user_count"] == 0
        assert data["today_new_users"] == 0
        assert Decimal(data["today_recharge_total"]) == Decimal("0")
        assert data["pending_ticket_count"] == 0

    def test_user_counts(self, client, db_session):
        admin = _make_admin(db_session)
        db_session.add_all([
            User(email="u1@example.com", role="user", status="active"),
            User(email="u2@example.com", role="member", status="active"),
            User(email="u3@example.com", role="distributor", status="active"),
            User(email="u4@example.com", role="agent", status="active"),
        ])
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 4
        assert data["regular_user_count"] == 1
        assert data["member_count"] == 1
        assert data["distributor_count"] == 1
        assert data["agent_count"] == 1

    def test_pending_ticket_count(self, client, db_session):
        admin = _make_admin(db_session)
        user = User(email="u@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        db_session.add_all([
            Ticket(user_id=user.id, amount=Decimal("100"), payment_method="m1", status="pending"),
            Ticket(user_id=user.id, amount=Decimal("200"), payment_method="m2", status="paid"),
            Ticket(user_id=user.id, amount=Decimal("300"), payment_method="m3", status="pending"),
        ])
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["pending_ticket_count"] == 2

    def test_today_recharge_total(self, client, db_session):
        """今日已批准充值总额"""
        admin = _make_admin(db_session)
        user = User(email="u@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        db_session.add_all([
            Recharge(user_id=user.id, amount=888, target_role="member", status="approved"),
            Recharge(user_id=user.id, amount=5000, target_role="distributor", status="approved"),
            Recharge(user_id=user.id, amount=10000, target_role="agent", status="pending"),
        ])
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 888 + 5000 = 5888 (pending 不计)
        assert Decimal(data["today_recharge_total"]) == Decimal("5888")

    def test_today_new_users(self, client, db_session):
        admin = _make_admin(db_session)
        db_session.add_all([
            User(email="u1@example.com", role="user", status="active"),
            User(email="u2@example.com", role="user", status="active"),
        ])
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["today_new_users"] == 2
