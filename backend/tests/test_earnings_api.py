"""Tests for earnings API endpoints。"""

from datetime import datetime, timezone
from decimal import Decimal

from app.core.security import create_access_token
from app.models.commission_record import CommissionRecord
from app.models.user import User


def _make_record(db, user_id, amount, rtype, source_user_id=None, business_id=None):
    r = CommissionRecord(
        user_id=user_id,
        amount=Decimal(amount),
        type=rtype,
        source_user_id=source_user_id,
        business_id=business_id or f"test_{rtype}_{user_id}_{amount}",
    )
    db.add(r)
    db.commit()
    return r


class TestEarningsAPI:
    def test_earnings_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/earnings")
        assert resp.status_code == 401

    def test_earnings_empty(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["pending_balance"] == "0.00"
        assert data["records"] == []
        assert data["total"] == 0

    def test_earnings_with_records(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        _make_record(db_session, user.id, "100.00", "first_reward", business_id="b1")
        _make_record(db_session, user.id, "200.00", "followup_reward", business_id="b2")

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["pending_balance"] == "300.00"
        assert len(data["records"]) == 2

    def test_earnings_filter_by_type(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        _make_record(db_session, user.id, "100.00", "first_reward", business_id="b1")
        _make_record(db_session, user.id, "200.00", "followup_reward", business_id="b2")

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings?type=first_reward",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["type"] == "first_reward"

    def test_earnings_invalid_type(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings?type=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_earnings_pagination(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        for i in range(10):
            _make_record(db_session, user.id, "10.00", "first_reward", business_id=f"b{i}")

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings?limit=5&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 5
        assert data["total"] == 10

    def test_earnings_source_email(self, client, db_session):
        """验证 source_email 字段返回"""
        source = User(email="source@example.com", role="distributor", status="active")
        user = User(email="earner@example.com", role="distributor", status="active")
        db_session.add_all([source, user])
        db_session.commit()
        _make_record(db_session, user.id, "100.00", "first_reward",
                     source_user_id=source.id, business_id="b1")

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/earnings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        record = resp.json()["records"][0]
        assert record["source_email"] == "source@example.com"
