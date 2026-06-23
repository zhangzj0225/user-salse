"""Tests for app.schemas.auth — Pydantic validation."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, SendEmailCodeRequest, UserInfo
from app.models.user import User


class TestSendEmailCodeRequest:
    def test_accepts_valid_email(self):
        req = SendEmailCodeRequest(email="test@example.com")
        assert req.email == "test@example.com"

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            SendEmailCodeRequest(email="not-an-email")

    def test_rejects_empty_email(self):
        with pytest.raises(ValidationError):
            SendEmailCodeRequest(email="")

    def test_default_scene_is_login(self):
        req = SendEmailCodeRequest(email="test@example.com")
        assert req.scene == "login"

    def test_rejects_invalid_scene(self):
        with pytest.raises(ValidationError):
            SendEmailCodeRequest(email="test@example.com", scene="invalid")


class TestLoginRequest:
    def test_accepts_valid_request(self):
        req = LoginRequest(email="test@example.com", code="123456")
        assert req.email == "test@example.com"
        assert req.code == "123456"

    def test_login_request_no_referral_code_field(self):
        """LoginRequest has no referral_code field."""
        req = LoginRequest(email="test@example.com", code="123456")
        assert not hasattr(req, "referral_code") or req.model_dump().get("referral_code") is None


class TestUserInfo:
    def test_from_orm_model(self, db_session):
        user = User(email="test@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        info = UserInfo.model_validate(user)
        assert info.id == user.id
        assert info.email == "test@example.com"
        assert info.role == "distributor"
        assert info.status == "active"

    def test_handles_none_fields(self, db_session):
        user = User(email="test@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        info = UserInfo.model_validate(user)
        assert info.nickname is None
        assert info.avatar_url is None
