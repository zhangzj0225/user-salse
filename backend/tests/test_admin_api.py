"""Integration tests for admin API endpoints."""

import bcrypt
import pytest

from app.models.admin_user import AdminUser


class TestAdminLogin:
    @pytest.fixture
    def admin_user(self, db_session):
        admin = AdminUser(
            username="admin",
            password_hash=bcrypt.hashpw(
                b"password123", bcrypt.gensalt()
            ).decode(),
        )
        db_session.add(admin)
        db_session.commit()
        return admin

    def test_returns_200_with_token_and_admin(self, client, admin_user):
        response = client.post(
            "/api/v1/auth/admin-login",
            json={"username": "admin", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data["data"]
        assert data["data"]["admin"]["username"] == "admin"

    def test_returns_401_on_wrong_password(self, client, admin_user):
        response = client.post(
            "/api/v1/auth/admin-login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_returns_401_on_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/admin-login",
            json={"username": "ghost", "password": "password123"},
        )
        assert response.status_code == 401

    def test_returns_422_on_missing_fields(self, client):
        response = client.post("/api/v1/auth/admin-login", json={})
        assert response.status_code == 422


class TestAdminMe:
    @pytest.fixture
    def admin_token(self, client, db_session):
        admin = AdminUser(
            username="admin",
            password_hash=bcrypt.hashpw(
                b"password123", bcrypt.gensalt()
            ).decode(),
        )
        db_session.add(admin)
        db_session.commit()

        resp = client.post(
            "/api/v1/auth/admin-login",
            json={"username": "admin", "password": "password123"},
        )
        return resp.json()["data"]["token"]

    def test_returns_200_with_admin_info(self, client, admin_token):
        response = client.get(
            "/api/v1/admin/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["username"] == "admin"

    def test_returns_401_without_token(self, client):
        response = client.get("/api/v1/admin/me")
        assert response.status_code == 401

    def test_returns_401_with_invalid_token(self, client):
        response = client.get(
            "/api/v1/admin/me",
            headers={"Authorization": "Bearer garbage"},
        )
        assert response.status_code == 401

    def test_returns_403_with_user_token(self, client, db_session):
        # Create user first (FR-1: login requires existing user)
        from app.models.user import User
        db_session.add(User(email="test@example.com", role="distributor", status="active"))
        db_session.flush()

        # Login as regular user
        client.post("/api/v1/auth/send-email-code", json={"email": "test@example.com"})
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "code": "123456"},
        )
        user_token = resp.json()["data"]["token"]

        # Try to access admin endpoint with user token
        response = client.get(
            "/api/v1/admin/me",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403
