"""Tests for quota API endpoints。"""

from app.core.security import create_access_token
from app.models.user import User


class TestQuotaAPI:
    def test_get_quota_requires_auth(self, client):
        resp = client.get("/api/v1/quota")
        assert resp.status_code == 401

    def test_get_quota_agent_success(self, client, db_session):
        user = User(email="agent@example.com", role="agent", status="active",
                    account_quota=22, account_used=5)
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="agent", token_type="user")
        resp = client.get(
            "/api/v1/quota",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "agent"
        assert data["account_quota"] == 22
        assert data["account_used"] == 5
        assert data["remaining"] == 17
        assert data["can_replenish"] is False
        assert data["sales_records"] == []

    def test_get_quota_distributor_success(self, client, db_session):
        user = User(email="dist@example.com", role="distributor", status="active",
                    account_quota=11, account_used=3)
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/quota",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["remaining"] == 8

    def test_get_quota_zero_shows_can_replenish(self, client, db_session):
        """额度为 0 时 can_replenish=True"""
        user = User(email="zero@example.com", role="agent", status="active",
                    account_quota=0, account_used=0)
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="agent", token_type="user")
        resp = client.get(
            "/api/v1/quota",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining"] == 0
        assert data["can_replenish"] is True
