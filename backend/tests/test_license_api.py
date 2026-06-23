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
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/license",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_get_license_success(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id,
            source="payment", source_id=1, status="unused",
        )
        db_session.add(license_obj)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/users/me/license",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == code
        assert data["status"] == "unused"


class TestVerifyLicenseAPI:
    def test_requires_api_key(self, client, db_session):
        """缺少 X-API-Key → 422"""
        resp = client.post("/api/v1/license/verify", json={
            "code": "test",
        })
        assert resp.status_code == 422

    def test_invalid_api_key(self, client, db_session):
        """错误 API Key → 401"""
        resp = client.post(
            "/api/v1/license/verify",
            json={"code": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_verify_success(self, client, db_session):
        """正常验证"""
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id,
            source="payment", source_id=1, status="unused",
        )
        db_session.add(license_obj)
        db_session.commit()

        resp = client.post(
            "/api/v1/license/verify",
            json={"code": code},
            headers={"X-API-Key": settings.LICENSE_API_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_verify_already_activated(self, client, db_session):
        """已激活 → 无效"""
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        code = _generate_license_code(user.id, nonce="abcd1234")
        license_obj = License(
            code=code, user_id=user.id,
            source="payment", source_id=1, status="activated",
        )
        db_session.add(license_obj)
        db_session.commit()

        resp = client.post(
            "/api/v1/license/verify",
            json={"code": code},
            headers={"X-API-Key": settings.LICENSE_API_KEY},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
