"""Tests for license API endpoints。"""

from app.core.config import settings
from app.core.security import create_access_token
from app.models.license import License
from app.models.user import User
from app.services.license_service import _generate_license_code


class TestGetMyLicenseAPI:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/license")
        assert resp.status_code == 401

    def test_no_license_404(self, client, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/license",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_get_license_success(self, client, db_session):
        user = User(email="user@example.com", role="member", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, "user@example.com", nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id, email="user@example.com",
            source="recharge", source_id=1, status="unused",
        )
        db_session.add(license_obj)
        db_session.commit()

        token = create_access_token(subject=user.id, role="member", token_type="user")
        resp = client.get(
            "/api/v1/users/me/license",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == code
        assert data["email"] == "user@example.com"
        assert data["status"] == "unused"


class TestVerifyLicenseAPI:
    def test_requires_api_key(self, client, db_session):
        """缺少 X-API-Key → 422"""
        resp = client.post("/api/v1/license/verify", json={
            "code": "test", "email": "user@example.com",
        })
        assert resp.status_code == 422

    def test_invalid_api_key(self, client, db_session):
        """错误 API Key → 401"""
        resp = client.post(
            "/api/v1/license/verify",
            json={"code": "test", "email": "user@example.com"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_verify_success(self, client, db_session):
        """正常验证激活"""
        user = User(email="user@example.com", role="member", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, "user@example.com", nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id, email="user@example.com",
            source="recharge", source_id=1, status="unused",
        )
        db_session.add(license_obj)
        db_session.commit()

        resp = client.post(
            "/api/v1/license/verify",
            json={"code": code, "email": "user@example.com"},
            headers={"X-API-Key": settings.LICENSE_API_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "成功" in data["message"]

    def test_verify_already_activated(self, client, db_session):
        """重复激活 → 失败"""
        user = User(email="user@example.com", role="member", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, "user@example.com", nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id, email="user@example.com",
            source="recharge", source_id=1, status="activated",
        )
        db_session.add(license_obj)
        db_session.commit()

        resp = client.post(
            "/api/v1/license/verify",
            json={"code": code, "email": "user@example.com"},
            headers={"X-API-Key": settings.LICENSE_API_KEY},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_verify_wrong_email(self, client, db_session):
        """邮箱不匹配 → 失败"""
        user = User(email="user@example.com", role="member", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, "user@example.com", nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id, email="user@example.com",
            source="recharge", source_id=1, status="unused",
        )
        db_session.add(license_obj)
        db_session.commit()

        resp = client.post(
            "/api/v1/license/verify",
            json={"code": code, "email": "wrong@example.com"},
            headers={"X-API-Key": settings.LICENSE_API_KEY},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False
