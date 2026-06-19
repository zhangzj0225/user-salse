"""Tests for sales API endpoints。"""

from app.core.security import create_access_token
from app.models.user import User


class TestSalesAPI:
    def test_sell_requires_auth(self, client):
        resp = client.post("/api/v1/sales", json={"customer_email": "c@example.com"})
        assert resp.status_code == 401

    def test_sell_success_agent(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        db_session.add(agent)
        db_session.commit()

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] is not None
        assert data["recharge_id"] is not None
        assert data["remaining_quota"] == 4

    def test_sell_success_distributor(self, client, db_session):
        dist = User(email="dist@example.com", role="distributor", status="active",
                    account_quota=11, account_used=0)
        db_session.add(dist)
        db_session.commit()

        token = create_access_token(subject=dist.id, role="distributor", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["remaining_quota"] == 10

    def test_sell_user_forbidden(self, client, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_sell_zero_quota(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=1, account_used=1)
        db_session.add(agent)
        db_session.commit()

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "额度不足" in resp.json()["detail"]

    def test_sell_duplicate_email(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        existing = User(email="taken@example.com", role="user", status="active")
        db_session.add_all([agent, existing])
        db_session.commit()

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "taken@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "已注册" in resp.json()["detail"]

    def test_sell_invalid_email(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        db_session.add(agent)
        db_session.commit()

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "not-an-email"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
