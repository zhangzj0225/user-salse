"""Integration tests for auth API endpoints."""


class TestSendEmailCode:
    def test_returns_200_with_code_in_mock_mode(self, client):
        response = client.post("/api/v1/auth/send-email-code", json={"email": "test@example.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["message"] == "验证码已发送"
        assert data["data"]["code"] == "123456"

    def test_returns_422_on_invalid_email(self, client):
        response = client.post("/api/v1/auth/send-email-code", json={"email": "not-an-email"})
        assert response.status_code == 422

    def test_returns_422_on_missing_email(self, client):
        response = client.post("/api/v1/auth/send-email-code", json={})
        assert response.status_code == 422


class TestLogin:
    def _send_code(self, client, email="test@example.com"):
        client.post("/api/v1/auth/send-email-code", json={"email": email})

    def test_returns_200_with_token_and_user(self, client):
        self._send_code(client)
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data["data"]
        assert data["data"]["user"]["email"] == "test@example.com"

    def test_returns_400_on_wrong_code(self, client):
        self._send_code(client)
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "999999"})
        assert response.status_code == 400

    def test_returns_400_when_no_code_sent(self, client):
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        assert response.status_code == 400

    def test_returns_422_on_invalid_body(self, client):
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com"})
        assert response.status_code == 422

    def test_creates_user_on_first_login(self, client):
        self._send_code(client)
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        user_data = response.json()["data"]["user"]
        assert user_data["role"] == "user"
        assert user_data["status"] == "active"

    def test_returns_same_user_on_second_login(self, client):
        self._send_code(client)
        first = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        first_id = first.json()["data"]["user"]["id"]

        self._send_code(client)
        second = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        second_id = second.json()["data"]["user"]["id"]
        assert first_id == second_id


class TestUsersMe:
    def _login(self, client, email="test@example.com"):
        client.post("/api/v1/auth/send-email-code", json={"email": email})
        resp = client.post("/api/v1/auth/login", json={"email": email, "code": "123456"})
        return resp.json()["data"]["token"]

    def test_returns_200_with_user_info(self, client):
        token = self._login(client)
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["data"]["email"] == "test@example.com"

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
        payload = {"sub": 1, "role": "user", "type": "user", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401


class TestHealth:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
