"""Tests for sales API endpoints。"""

from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User

MOCK_CODE = "123456"


def _make_code(db, email, scene="sale_verify", code=MOCK_CODE):
    record = EmailVerificationCode(
        email=email,
        code=code,
        scene=scene,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(record)
    db.commit()


class TestSalesAPI:
    def test_sell_requires_auth(self, client):
        resp = client.post("/api/v1/sales", json={
            "customer_email": "c@example.com",
            "verification_code": MOCK_CODE,
        })
        assert resp.status_code == 401

    def test_sell_success_agent(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        db_session.add(agent)
        db_session.commit()
        _make_code(db_session, "customer@example.com")

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com", "verification_code": MOCK_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] is not None
        assert data["payment_id"] is not None
        assert data["remaining_quota"] == 4

    def test_sell_success_distributor(self, client, db_session):
        dist = User(email="dist@example.com", role="distributor", status="active",
                    account_quota=11, account_used=0)
        db_session.add(dist)
        db_session.commit()
        _make_code(db_session, "customer@example.com")

        token = create_access_token(subject=dist.id, role="distributor", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com", "verification_code": MOCK_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["remaining_quota"] == 10

    def test_sell_zero_quota(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=1, account_used=1)
        db_session.add(agent)
        db_session.commit()
        _make_code(db_session, "customer@example.com")

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com", "verification_code": MOCK_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "额度不足" in resp.json()["detail"]

    def test_sell_duplicate_email(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        existing = User(email="taken@example.com", role="distributor", status="active")
        db_session.add_all([agent, existing])
        db_session.commit()
        _make_code(db_session, "taken@example.com")

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "taken@example.com", "verification_code": MOCK_CODE},
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
            json={"customer_email": "not-an-email", "verification_code": MOCK_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_sell_invalid_verification_code(self, client, db_session):
        """S2: 验证码错误"""
        agent = User(email="agent@example.com", role="agent", status="active",
                     account_quota=5, account_used=0)
        db_session.add(agent)
        db_session.commit()
        _make_code(db_session, "customer@example.com")

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.post(
            "/api/v1/sales",
            json={"customer_email": "customer@example.com", "verification_code": "000000"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "验证码" in resp.json()["detail"]

    def test_sell_missing_verification_code(self, client, db_session):
        """缺少 verification_code 字段"""
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
        assert resp.status_code == 422
