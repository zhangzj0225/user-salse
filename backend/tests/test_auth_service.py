"""Tests for app.services.auth_service — MockAuthService behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.auth_service import MockAuthService, EmailAuthService, get_auth_service
def _make_user(db_session, email="test@example.com", role="distributor"):
    """PRD v2: 预创建用户"""
    from app.models.user import User
    u = User(email=email, role=role, status="active")
    db_session.add(u)
    db_session.commit()
    return u



def _make_user(db, email, role="distributor"):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    u = User(email=email, role=role, status="active")
    db.add(u)
    db.flush()
    return u


class TestMockAuthServiceSendEmailCode:
    def test_creates_email_record_in_db(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        code = service.send_email_code("test@example.com", "login", db_session)

        records = db_session.query(EmailVerificationCode).filter(
            EmailVerificationCode.email == "test@example.com"
        ).all()
        assert len(records) == 1
        assert records[0].code == "123456"
        assert records[0].scene == "login"
        assert records[0].verified is False

    def test_returns_mock_code(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        code = service.send_email_code("test@example.com", "login", db_session)
        assert code == "123456"

    def test_sets_expiry_5_minutes_in_future(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        record = db_session.query(EmailVerificationCode).first()
        now = datetime.now(timezone.utc)
        delta = record.expires_at.replace(tzinfo=timezone.utc) - now
        assert timedelta(minutes=4, seconds=30) < delta < timedelta(minutes=5, seconds=30)

    def test_send_register_scene_creates_correct_record(self, db_session):
        """AC1: send-email-code with scene='register' creates DB record with scene='register'."""
        service = MockAuthService()
        code = service.send_email_code("new@example.com", "register", db_session)

        record = db_session.query(EmailVerificationCode).filter(
            EmailVerificationCode.email == "new@example.com",
            EmailVerificationCode.scene == "register",
        ).first()
        assert record is not None
        assert record.code == code
        assert record.scene == "register"
        assert record.verified is False


class TestMockAuthServiceAuthenticate:
    def test_returns_user_and_token_on_valid_code(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        user, token = service.authenticate("test@example.com", "123456", db_session)
        assert isinstance(user, User)
        assert user.email == "test@example.com"
        assert isinstance(token, str)
        assert len(token) > 0

    def test_creates_new_user_on_first_login(self, db_session):
        _make_user(db_session, "test@example.com")
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        user, _ = service.authenticate("test@example.com", "123456", db_session)
        assert user.email == "test@example.com"
        assert user.role == "distributor"
        assert user.status == "active"
        assert user.parent_id is None
    def test_returns_existing_user_on_second_login(self, db_session):
    def test_rejects_nonexistent_user(self, db_session):
        """PRD v2: 不存在的用户登录时抛出 ValueError"""
        # 不存在的用户无法发送验证码
        with pytest.raises(ValueError, match="用户不存在"):
            service.send_email_code("noone@example.com", "login", db_session)
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        first_user, _ = service.authenticate("test@example.com", "123456", db_session)

        service.send_email_code("test@example.com", "login", db_session)
        second_user, _ = service.authenticate("test@example.com", "123456", db_session)
        assert second_user.id == first_user.id

    def test_marks_email_record_verified(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        service.authenticate("test@example.com", "123456", db_session)
        record = db_session.query(EmailVerificationCode).filter(
            EmailVerificationCode.email == "test@example.com"
        ).first()
        assert record.verified is True

    def test_raises_value_error_on_wrong_code(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        with pytest.raises(ValueError, match="验证码错误"):
            service.authenticate("test@example.com", "999999", db_session)

    def test_raises_value_error_when_no_email_record_exists(self, db_session):
        _make_user(db_session)
        service = MockAuthService()
        with pytest.raises(ValueError, match="验证码错误或已过期"):
            service.authenticate("test@example.com", "123456", db_session)

    def test_raises_value_error_when_email_record_expired(self, db_session):
        _make_user(db_session)
        service = MockAuthService()
        record = EmailVerificationCode(
            email="test@example.com",
            code="123456",
            scene="login",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(record)
        db_session.commit()

        with pytest.raises(ValueError, match="验证码错误或已过期"):
            service.authenticate("test@example.com", "123456", db_session)

    def test_jwt_token_has_correct_type(self, db_session):
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        _, token = service.authenticate("test@example.com", "123456", db_session)

        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        assert payload["type"] == "user"


class TestEmailAuthService:
    """EmailAuthService 现已实现真实 SMTP 发送。

    send_email_code 会尝试连接 SMTP 服务器，无配置时抛连接异常（非 NotImplementedError）。
    authenticate / register 逻辑与 MockAuthService 一致，复用父类验证码校验。
    """

    def test_send_email_code_writes_db_record(self, db_session, monkeypatch):
        """验证码写入 DB（SMTP 发送被 mock 避免真实网络调用）。"""
        _make_user(db_session, "test@example.com")
        _make_user(db_session)
        service = EmailAuthService()

        # mock SMTP 发送，避免真实网络调用
        def fake_smtp(self, to_email, code, scene):
            pass
        monkeypatch.setattr(EmailAuthService, "_send_email_smtp", fake_smtp)

        code = service.send_email_code("test@example.com", "login", db_session)
        assert len(code) == 6
        assert code.isdigit()

        from app.models.email_verification_code import EmailVerificationCode
        record = db_session.query(EmailVerificationCode).filter_by(
            email="test@example.com", scene="login"
        ).first()
        assert record is not None
        assert record.code == code

    def test_authenticate_verifies_code(self, db_session, monkeypatch):
        """authenticate 正确校验验证码并创建用户。"""
        """authenticate 正确校验验证码并返回用户。"""
        _make_user(db_session, "auth_test@example.com")
        service = EmailAuthService()

        def fake_smtp(self, to_email, code, scene):
            pass
        monkeypatch.setattr(EmailAuthService, "_send_email_smtp", fake_smtp)

        code = service.send_email_code("auth_test@example.com", "login", db_session)
        user, token = service.authenticate("auth_test@example.com", code, db_session)
        assert user.email == "auth_test@example.com"
        assert token is not None


class TestGetAuthService:
    def test_returns_mock_service_when_auth_mode_is_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "mock")
        service = get_auth_service()
        assert isinstance(service, MockAuthService)

    def test_returns_email_service_when_auth_mode_is_email(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "email")
        service = get_auth_service()
        assert isinstance(service, EmailAuthService)
