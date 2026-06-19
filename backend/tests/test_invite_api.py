"""Tests for invite code API endpoints。"""

from app.core.security import create_access_token
from app.models.user import User


class TestGenerateInviteCodeAPI:
    def test_generate_requires_auth(self, client):
        resp = client.post("/api/v1/invite-codes")
        assert resp.status_code == 401

    def test_generate_success(self, client, db_session):
        user = User(email="api@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "code" in data
        assert "." in data["code"]
        assert data["generator_id"] == user.id
        assert data["used_by"] is None

    def test_generate_multiple_codes(self, client, db_session):
        user = User(email="multi@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp1 = client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp2 = client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200


class TestListInviteCodesAPI:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/invite-codes")
        assert resp.status_code == 401

    def test_list_returns_user_codes(self, client, db_session):
        user = User(email="lister@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        # 生成 2 个邀请码
        client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = client.get(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert all(d["generator_id"] == user.id for d in data)

    def test_list_empty(self, client, db_session):
        user = User(email="empty@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestVerifyInviteCodeAPI:
    def test_verify_requires_auth(self, client):
        resp = client.post(
            "/api/v1/invite-codes/verify",
            json={"code": "somecode"},
        )
        assert resp.status_code == 401

    def test_verify_valid_code(self, client, db_session):
        user = User(email="verify@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        # 先生成邀请码
        gen_resp = client.post(
            "/api/v1/invite-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        code = gen_resp.json()["data"]["code"]

        # 验证
        resp = client.post(
            "/api/v1/invite-codes/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": code},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is True
        assert data["generator_id"] == user.id
        assert data["used"] is False

    def test_verify_invalid_format(self, client, db_session):
        user = User(email="invalid@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/invite-codes/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "no-dot-here"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is False
        assert data["generator_id"] is None

    def test_verify_nonexistent_code(self, client, db_session):
        user = User(email="nonexist@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/invite-codes/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "99.abcdef0123456789"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["valid"] is False
