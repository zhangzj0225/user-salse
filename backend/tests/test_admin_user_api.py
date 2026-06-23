"""Tests for Story 4.1 用户管理。"""

import pytest
from decimal import Decimal

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.user import User


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.commit()
    return admin


def _make_user(db, email, role="distributor", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.commit()
    return u


class TestListUsersAPI:
    def test_requires_admin_auth(self, client):
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    def test_requires_admin_role(self, client, db_session):
        user = _make_user(db_session, "user@example.com")
        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_list_empty(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["users"] == []
        assert resp.json()["total"] == 0

    def test_list_with_users(self, client, db_session):
        admin = _make_admin(db_session)
        _make_user(db_session, "u1@example.com", "distributor")
        _make_user(db_session, "u2@example.com", "distributor")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2

    def test_search_by_email(self, client, db_session):
        admin = _make_admin(db_session)
        _make_user(db_session, "alice@example.com")
        _make_user(db_session, "bob@example.com")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users?search=alice",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["users"][0]["email"] == "alice@example.com"

    def test_filter_by_role(self, client, db_session):
        admin = _make_admin(db_session)
        _make_user(db_session, "u1@example.com", "distributor")
        _make_user(db_session, "u2@example.com", "distributor")
        _make_user(db_session, "u3@example.com", "agent")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users?role=agent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["users"][0]["role"] == "agent"

    def test_invalid_role(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users?role=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_pagination(self, client, db_session):
        admin = _make_admin(db_session)
        for i in range(5):
            _make_user(db_session, f"u{i}@example.com")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users?limit=2&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) == 2
        assert data["total"] == 5

    def test_parent_email_included(self, client, db_session):
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", "distributor", parent_id=parent.id)

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users?search=child",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        user_data = resp.json()["users"][0]
        assert user_data["parent_email"] == "parent@example.com"


class TestUserDetailAPI:
    def test_get_detail_success(self, client, db_session):
        admin = _make_admin(db_session)
        user = _make_user(db_session, "detail@example.com", "agent")

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            f"/api/v1/admin/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "detail@example.com"
        assert data["role"] == "agent"
        assert data["direct_downline_count"] == 0
        assert data["total_downline_count"] == 0
        assert data["total_commission"] == "0.00"
        assert data["available_balance"] == "0.00"

    def test_get_detail_with_earnings(self, client, db_session):
        admin = _make_admin(db_session)
        user = _make_user(db_session, "earner@example.com")
        # Add commission
        record = CommissionRecord(
            user_id=user.id, amount=Decimal("500.00"), type="first_reward",
            business_id="test_detail_1",
        )
        db_session.add(record)
        db_session.commit()

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            f"/api/v1/admin/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_commission"] == "500.00"
        assert data["available_balance"] == "500.00"

    def test_get_detail_with_team(self, client, db_session):
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        child1 = _make_user(db_session, "c1@example.com", "distributor", parent_id=parent.id)
        child2 = _make_user(db_session, "c2@example.com", "distributor", parent_id=parent.id)
        grandchild = _make_user(db_session, "gc@example.com", "distributor", parent_id=child1.id)

        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            f"/api/v1/admin/users/{parent.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["direct_downline_count"] == 2
        assert data["total_downline_count"] == 3  # 2 children + 1 grandchild

    def test_get_detail_nonexistent(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/users/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
