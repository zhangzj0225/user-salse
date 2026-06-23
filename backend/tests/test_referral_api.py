"""Tests for referral code API endpoints。"""

from app.core.security import create_access_token
from app.models.user import User


class TestGetReferralCodeAPI:
    def test_get_requires_auth(self, client):
        resp = client.get("/api/v1/referral-code")
        assert resp.status_code == 401

    def test_get_creates_and_returns_code(self, client, db_session):
        user = User(email="api@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/referral-code",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "code" in data
        assert "." in data["code"]
        assert data["user_id"] == user.id

    def test_get_returns_same_code_on_repeat(self, client, db_session):
        """持久码：多次调用返回同一个推荐码。"""
        user = User(email="multi@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp1 = client.get(
            "/api/v1/referral-code",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp2 = client.get(
            "/api/v1/referral-code",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["data"]["code"] == resp2.json()["data"]["code"]
