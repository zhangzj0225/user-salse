"""Tests for admin authentication."""

import bcrypt
import pytest

from app.models.admin_user import AdminUser
from app.services.auth_service import AdminAuthService


class TestAdminAuthService:
    @pytest.fixture
    def admin_user(self, db_session):
        admin = AdminUser(
            username="admin",
            password_hash=bcrypt.hashpw(
                b"password123", bcrypt.gensalt()
            ).decode(),
        )
        db_session.add(admin)
        db_session.commit()
        return admin

    def test_authenticate_returns_admin_and_token(self, db_session, admin_user):
        service = AdminAuthService()
        admin, token = service.authenticate("admin", "password123", db_session)
        assert admin.id == admin_user.id
        assert admin.username == "admin"
        assert isinstance(token, str)
        assert len(token) > 0

    def test_authenticate_raises_on_wrong_password(self, db_session, admin_user):
        service = AdminAuthService()
        with pytest.raises(ValueError, match="Invalid credentials"):
            service.authenticate("admin", "wrongpassword", db_session)

    def test_authenticate_raises_on_nonexistent_user(self, db_session):
        service = AdminAuthService()
        with pytest.raises(ValueError, match="Invalid credentials"):
            service.authenticate("nonexistent", "password123", db_session)

    def test_jwt_token_has_admin_type(self, db_session, admin_user):
        service = AdminAuthService()
        _, token = service.authenticate("admin", "password123", db_session)

        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        assert payload["type"] == "admin"
        assert payload["role"] == "admin"
