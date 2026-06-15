"""Tests for app.schemas.auth — Pydantic validation."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, SendSmsRequest, UserInfo
from app.models.user import User


class TestSendSmsRequest:
    def test_accepts_valid_phone(self):
        req = SendSmsRequest(phone="13800138000")
        assert req.phone == "13800138000"

    def test_rejects_phone_too_short(self):
        with pytest.raises(ValidationError):
            SendSmsRequest(phone="12345")

    def test_rejects_phone_with_letters(self):
        with pytest.raises(ValidationError):
            SendSmsRequest(phone="1380013800a")

    def test_rejects_empty_phone(self):
        with pytest.raises(ValidationError):
            SendSmsRequest(phone="")


class TestLoginRequest:
    def test_accepts_valid_request(self):
        req = LoginRequest(phone="13800138000", sms_code="123456")
        assert req.phone == "13800138000"
        assert req.sms_code == "123456"

    def test_accepts_with_invite_code(self):
        req = LoginRequest(phone="13800138000", sms_code="123456", invite_code="ABC123")
        assert req.invite_code == "ABC123"

    def test_rejects_sms_code_too_short(self):
        with pytest.raises(ValidationError):
            LoginRequest(phone="13800138000", sms_code="12345")

    def test_rejects_sms_code_too_long(self):
        with pytest.raises(ValidationError):
            LoginRequest(phone="13800138000", sms_code="1234567")

    def test_rejects_sms_code_with_letters(self):
        with pytest.raises(ValidationError):
            LoginRequest(phone="13800138000", sms_code="abcdef")

    def test_rejects_invalid_phone(self):
        with pytest.raises(ValidationError):
            LoginRequest(phone="99900138000", sms_code="123456")


class TestUserInfo:
    def test_from_orm_model(self, db_session):
        user = User(openid="test", phone="13800138000", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        info = UserInfo.model_validate(user)
        assert info.id == user.id
        assert info.phone == "13800138000"
        assert info.role == "user"
        assert info.status == "active"

    def test_handles_none_fields(self, db_session):
        user = User(openid="test", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        info = UserInfo.model_validate(user)
        assert info.phone is None
        assert info.nickname is None
