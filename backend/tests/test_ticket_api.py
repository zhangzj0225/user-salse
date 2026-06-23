"""Tests for withdrawal ticket API endpoints。"""

from decimal import Decimal

from app.core.security import create_access_token
from app.models.commission_record import CommissionRecord
from app.models.user import User


def _setup_user_with_balance(db, email="user@example.com", balance="500.00"):
    user = User(email=email, role="distributor", status="active")
    db.add(user)
    db.commit()
    r = CommissionRecord(
        user_id=user.id, amount=Decimal(balance), type="first_reward",
        business_id=f"test_{email}",
    )
    db.add(r)
    db.commit()
    return user


class TestCreateTicketAPI:
    def test_requires_auth(self, client):
        resp = client.post("/api/v1/users/me/tickets", json={
            "amount": "100", "payment_method": "支付宝:xxx",
        })
        assert resp.status_code == 401

    def test_create_success(self, client, db_session):
        user = _setup_user_with_balance(db_session)

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "200.00", "payment_method": "支付宝:xxx"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["available_balance"] == "300.00"

    def test_below_minimum(self, client, db_session):
        user = _setup_user_with_balance(db_session)

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "50", "payment_method": "支付宝:xxx"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "最低" in resp.json()["detail"]

    def test_exceeds_balance(self, client, db_session):
        user = _setup_user_with_balance(db_session, balance="100.00")

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "200", "payment_method": "支付宝:xxx"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "超过" in resp.json()["detail"]


class TestListTicketsAPI:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/tickets")
        assert resp.status_code == 401

    def test_empty_list(self, client, db_session):
        user = _setup_user_with_balance(db_session)

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["tickets"] == []
        assert resp.json()["total"] == 0

    def test_list_with_tickets(self, client, db_session):
        user = _setup_user_with_balance(db_session)

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        # 创建 2 个工单
        client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "100.00", "payment_method": "m1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "100.00", "payment_method": "m2"},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = client.get(
            "/api/v1/users/me/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_by_status(self, client, db_session):
        user = _setup_user_with_balance(db_session)

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        client.post(
            "/api/v1/users/me/tickets",
            json={"amount": "100.00", "payment_method": "m1"},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = client.get(
            "/api/v1/users/me/tickets?status=pending",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["tickets"][0]["status"] == "pending"
