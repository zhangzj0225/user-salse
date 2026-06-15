"""Integration tests for auth API endpoints."""

import pytest


class TestSendSms:
    def test_returns_200_with_code_in_mock_mode(self, client):
        response = client.post("/api/v1/auth/send-sms", json={"phone": "13800138000"})
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["message"] == "验证码已发送"
        assert data["data"]["code"] == "123456"

    def test_returns_422_on_invalid_phone(self, client):
        response = client.post("/api/v1/auth/send-sms", json={"phone": "12345"})
        assert response.status_code == 422

    def test_returns_422_on_missing_phone(self, client):
        response = client.post("/api/v1/auth/send-sms", json={})
        assert response.status_code == 422


class TestLogin:
    def _send_sms(self, client, phone="13800138000"):
        client.post("/api/v1/auth/send-sms", json={"phone": phone})

    def test_returns_200_with_token_and_user(self, client):
        self._send_sms(client)
        response = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data["data"]
        assert data["data"]["user"]["phone"] == "13800138000"

    def test_returns_400_on_wrong_code(self, client):
        self._send_sms(client)
        response = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "999999"})
        assert response.status_code == 400

    def test_returns_400_when_no_sms_sent(self, client):
        response = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "123456"})
        assert response.status_code == 400

    def test_returns_422_on_invalid_body(self, client):
        response = client.post("/api/v1/auth/login", json={"phone": "13800138000"})
        assert response.status_code == 422

    def test_creates_user_on_first_login(self, client):
        self._send_sms(client)
        response = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "123456"})
        user_data = response.json()["data"]["user"]
        assert user_data["role"] == "user"
        assert user_data["status"] == "active"

    def test_returns_same_user_on_second_login(self, client):
        self._send_sms(client)
        first = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "123456"})
        first_id = first.json()["data"]["user"]["id"]

        self._send_sms(client)
        second = client.post("/api/v1/auth/login", json={"phone": "13800138000", "sms_code": "123456"})
        second_id = second.json()["data"]["user"]["id"]
        assert first_id == second_id


class TestUsersMe:
    def _login(self, client, phone="13800138000"):
        client.post("/api/v1/auth/send-sms", json={"phone": phone})
        resp = client.post("/api/v1/auth/login", json={"phone": phone, "sms_code": "123456"})
        return resp.json()["data"]["token"]

    def test_returns_200_with_user_info(self, client):
        token = self._login(client)
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["data"]["phone"] == "13800138000"

    def test_returns_401_without_token(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401

    def test_returns_401_with_invalid_token(self, client):
        response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401

    def test_returns_401_with_expired_token(self, client):
        from datetime import datetime, timedelta, timezone
        import jwt
        from app.core.config import settings

        now = datetime.now(timezone.utc)
        expire = now - timedelta(hours=1)
        payload = {"sub": 1, "role": "user", "type": "wechat", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401


class TestHealth:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
