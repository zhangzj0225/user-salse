"""Tests for app.services.auth_service — MockAuthService behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.sms_record import SmsRecord
from app.models.user import User
from app.services.auth_service import MockAuthService, WechatAuthService, get_auth_service


class TestMockAuthServiceSendSms:
    def test_creates_sms_record_in_db(self, db_session):
        service = MockAuthService()
        code = service.send_sms_code("13800138000", db_session)

        records = db_session.query(SmsRecord).filter(SmsRecord.phone == "13800138000").all()
        assert len(records) == 1
        assert records[0].code == "123456"
        assert records[0].scene == "login"
        assert records[0].verified is False

    def test_returns_mock_code(self, db_session):
        service = MockAuthService()
        code = service.send_sms_code("13800138000", db_session)
        assert code == "123456"

    def test_sets_expiry_5_minutes_in_future(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)
        record = db_session.query(SmsRecord).first()
        now = datetime.now(timezone.utc)
        delta = record.expires_at.replace(tzinfo=timezone.utc) - now
        assert timedelta(minutes=4, seconds=30) < delta < timedelta(minutes=5, seconds=30)


class TestMockAuthServiceAuthenticate:
    def test_returns_user_and_token_on_valid_code(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)

        user, token = service.authenticate("13800138000", "123456", None, db_session)
        assert isinstance(user, User)
        assert user.phone == "13800138000"
        assert isinstance(token, str)
        assert len(token) > 0

    def test_creates_new_user_on_first_login(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)

        user, _ = service.authenticate("13800138000", "123456", None, db_session)
        assert user.openid == "mock_13800138000"
        assert user.role == "user"
        assert user.status == "active"

    def test_returns_existing_user_on_second_login(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)
        first_user, _ = service.authenticate("13800138000", "123456", None, db_session)

        service.send_sms_code("13800138000", db_session)
        second_user, _ = service.authenticate("13800138000", "123456", None, db_session)
        assert second_user.id == first_user.id

    def test_marks_sms_record_verified(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)

        service.authenticate("13800138000", "123456", None, db_session)
        record = db_session.query(SmsRecord).filter(SmsRecord.phone == "13800138000").first()
        assert record.verified is True

    def test_raises_value_error_on_wrong_code(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)

        with pytest.raises(ValueError, match="Invalid SMS code"):
            service.authenticate("13800138000", "999999", None, db_session)

    def test_raises_value_error_when_no_sms_record_exists(self, db_session):
        service = MockAuthService()
        with pytest.raises(ValueError, match="SMS code expired or not found"):
            service.authenticate("13800138000", "123456", None, db_session)

    def test_raises_value_error_when_sms_record_expired(self, db_session):
        service = MockAuthService()
        record = SmsRecord(
            phone="13800138000",
            code="123456",
            scene="login",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(record)
        db_session.commit()

        with pytest.raises(ValueError, match="SMS code expired or not found"):
            service.authenticate("13800138000", "123456", None, db_session)

    def test_jwt_token_has_correct_type(self, db_session):
        service = MockAuthService()
        service.send_sms_code("13800138000", db_session)
        _, token = service.authenticate("13800138000", "123456", None, db_session)

        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        assert payload["type"] == "wechat"


class TestWechatAuthService:
    def test_send_sms_raises_not_implemented(self, db_session):
        service = WechatAuthService()
        with pytest.raises(NotImplementedError):
            service.send_sms_code("13800138000", db_session)

    def test_authenticate_raises_not_implemented(self, db_session):
        service = WechatAuthService()
        with pytest.raises(NotImplementedError):
            service.authenticate("13800138000", "123456", None, db_session)


class TestGetAuthService:
    def test_returns_mock_service_when_auth_mode_is_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "mock")
        service = get_auth_service()
        assert isinstance(service, MockAuthService)

    def test_returns_wechat_service_when_auth_mode_is_wechat(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "wechat")
        service = get_auth_service()
        assert isinstance(service, WechatAuthService)
