"""Integration tests for auth API endpoints."""

from app.models.user import User


def _make_user(db, email="test@example.com", role="distributor"):
    """Create a test user in the DB."""
    u = User(email=email, role=role, status="active")
    db.add(u)
    db.flush()
    return u


class TestSendEmailCode:
    def test_returns_200_with_code_in_mock_mode(self, client, db_session):
        _make_user(db_session, "test@example.com")
        response = client.post("/api/v1/auth/send-email-code", json={"email": "test@example.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["message"] == "验证码已发送"
        assert data["data"]["code"] == "123456"

    def test_returns_400_for_nonexistent_user(self, client):
        """FR-1: login scene rejects non-existent users."""
        response = client.post("/api/v1/auth/send-email-code", json={"email": "nobody@example.com"})
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]

    def test_returns_200_for_sale_verify_scene(self, client):
        """sale_verify scene does not check user existence."""
        response = client.post("/api/v1/auth/send-email-code", json={"email": "newcustomer@example.com", "scene": "sale_verify"})
        assert response.status_code == 200

    def test_returns_422_on_invalid_email(self, client):
        response = client.post("/api/v1/auth/send-email-code", json={"email": "not-an-email"})
        assert response.status_code == 422

    def test_returns_422_on_missing_email(self, client):
        response = client.post("/api/v1/auth/send-email-code", json={})
        assert response.status_code == 422


class TestLogin:
    def _send_code(self, client, email="test@example.com"):
        client.post("/api/v1/auth/send-email-code", json={"email": email})

    def test_returns_200_with_token_and_user(self, client, db_session):
        _make_user(db_session, "test@example.com")
        self._send_code(client)
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data["data"]
        assert data["data"]["user"]["email"] == "test@example.com"

    def test_returns_400_on_wrong_code(self, client, db_session):
        _make_user(db_session, "test@example.com")
        self._send_code(client)
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "999999"})
        assert response.status_code == 400

    def test_returns_400_when_no_code_sent(self, client, db_session):
        _make_user(db_session, "test@example.com")
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        assert response.status_code == 400

    def test_returns_400_on_nonexistent_user(self, client):
        """FR-1: login rejects non-existent users."""
        response = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "code": "123456"})
        assert response.status_code == 400

    def test_returns_422_on_invalid_body(self, client):
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com"})
        assert response.status_code == 422

    def test_returns_same_user_on_second_login(self, client, db_session):
        _make_user(db_session, "test@example.com")
        self._send_code(client)
        first = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        first_id = first.json()["data"]["user"]["id"]

        self._send_code(client)
        second = client.post("/api/v1/auth/login", json={"email": "test@example.com", "code": "123456"})
        second_id = second.json()["data"]["user"]["id"]
        assert first_id == second_id


class TestUsersMe:
    def _login(self, client, db_session, email="test@example.com"):
        _make_user(db_session, email)
        client.post("/api/v1/auth/send-email-code", json={"email": email})
        resp = client.post("/api/v1/auth/login", json={"email": email, "code": "123456"})
        return resp.json()["data"]["token"]

    def test_returns_200_with_user_info(self, client, db_session):
        token = self._login(client, db_session)
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
        payload = {"sub": 1, "role": "distributor", "type": "user", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401

    def test_returns_403_with_admin_token(self, client):
        """Admin token must not pass user endpoint — token type check enforced."""
        import jwt
        from app.core.config import settings
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "1", "role": "admin", "type": "admin",
            "iat": now, "exp": now + timedelta(hours=1),
        }
        admin_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 403


class TestHealth:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
