"""Tests for app.services.auth_service — MockAuthService behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.email_verification_code import EmailVerificationCode
from app.models.invite_code import InviteCode
from app.models.user import User
from app.services.auth_service import MockAuthService, EmailAuthService, get_auth_service


class TestMockAuthServiceSendEmailCode:
    def test_creates_email_record_in_db(self, db_session):
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
        service = MockAuthService()
        code = service.send_email_code("test@example.com", "login", db_session)
        assert code == "123456"

    def test_sets_expiry_5_minutes_in_future(self, db_session):
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
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        user, token = service.authenticate("test@example.com", "123456", db_session)
        assert isinstance(user, User)
        assert user.email == "test@example.com"
        assert isinstance(token, str)
        assert len(token) > 0

    def test_creates_new_user_on_first_login(self, db_session):
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        user, _ = service.authenticate("test@example.com", "123456", db_session)
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.status == "active"
        assert user.parent_id is None  # cold-start: no parent

    def test_returns_existing_user_on_second_login(self, db_session):
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        first_user, _ = service.authenticate("test@example.com", "123456", db_session)

        service.send_email_code("test@example.com", "login", db_session)
        second_user, _ = service.authenticate("test@example.com", "123456", db_session)
        assert second_user.id == first_user.id

    def test_marks_email_record_verified(self, db_session):
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        service.authenticate("test@example.com", "123456", db_session)
        record = db_session.query(EmailVerificationCode).filter(
            EmailVerificationCode.email == "test@example.com"
        ).first()
        assert record.verified is True

    def test_raises_value_error_on_wrong_code(self, db_session):
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)

        with pytest.raises(ValueError, match="验证码错误"):
            service.authenticate("test@example.com", "999999", db_session)

    def test_raises_value_error_when_no_email_record_exists(self, db_session):
        service = MockAuthService()
        with pytest.raises(ValueError, match="验证码错误或已过期"):
            service.authenticate("test@example.com", "123456", db_session)

    def test_raises_value_error_when_email_record_expired(self, db_session):
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
        service = MockAuthService()
        service.send_email_code("test@example.com", "login", db_session)
        _, token = service.authenticate("test@example.com", "123456", db_session)

        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        assert payload["type"] == "user"


class TestMockAuthServiceRegister:
    def _make_parent(self, db_session, email: str = "parent@example.com") -> User:
        user = User(email=email, role="agent", status="active")
        db_session.add(user)
        db_session.flush()
        return user

    def _make_invite_code(self, db_session, generator_id: int, code: str = "INVCODE01") -> InviteCode:
        ic = InviteCode(code=code, generator_id=generator_id)
        db_session.add(ic)
        db_session.flush()
        return ic

    def _send_register_code(self, db_session, email: str = "new@example.com") -> None:
        service = MockAuthService()
        service.send_email_code(email, "register", db_session)

    def test_register_creates_user_with_parent_id(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        user, _ = service.register("new@example.com", "123456", ic.code, db_session)
        assert user.parent_id == parent.id

    def test_register_returns_user_and_token(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        user, token = service.register("new@example.com", "123456", ic.code, db_session)
        assert isinstance(user, User)
        assert user.email == "new@example.com"
        assert user.role == "user"
        assert user.status == "active"
        assert isinstance(token, str) and len(token) > 0

    def test_register_marks_email_code_verified(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        service.register("new@example.com", "123456", ic.code, db_session)

        record = db_session.query(EmailVerificationCode).filter(
            EmailVerificationCode.email == "new@example.com",
            EmailVerificationCode.scene == "register",
        ).first()
        assert record.verified is True

    def test_register_marks_invite_code_used(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        user, _ = service.register("new@example.com", "123456", ic.code, db_session)

        db_session.refresh(ic)
        assert ic.used_by == user.id
        assert ic.used_at is not None

    def test_register_raises_on_wrong_code(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        with pytest.raises(ValueError, match="验证码错误"):
            service.register("new@example.com", "999999", ic.code, db_session)

    def test_register_raises_on_expired_email_code(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        expired = EmailVerificationCode(
            email="new@example.com",
            code="123456",
            scene="register",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(expired)
        db_session.commit()

        service = MockAuthService()
        with pytest.raises(ValueError, match="验证码错误或已过期"):
            service.register("new@example.com", "123456", ic.code, db_session)

    def test_register_raises_on_invalid_invite_code(self, db_session):
        self._send_register_code(db_session)

        service = MockAuthService()
        with pytest.raises(ValueError, match="邀请码无效"):
            service.register("new@example.com", "123456", "NONEXISTENT", db_session)

    def test_register_raises_on_already_used_invite_code(self, db_session):
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        ic.used_by = parent.id  # mark as already used
        db_session.flush()
        self._send_register_code(db_session)

        service = MockAuthService()
        with pytest.raises(ValueError, match="邀请码已被使用"):
            service.register("new@example.com", "123456", ic.code, db_session)

    def test_register_raises_on_duplicate_email(self, db_session):
        parent = self._make_parent(db_session)
        # 使用另一个用户的邀请码（不是 parent 的），避免触发自推荐检查
        other = User(email="other@example.com", role="user", status="active")
        db_session.add(other)
        db_session.flush()
        ic = self._make_invite_code(db_session, other.id, "OTHERCODE")
        # parent's email is already taken
        self._send_register_code(db_session, "parent@example.com")

        service = MockAuthService()
        with pytest.raises(ValueError, match="邮箱已注册"):
            service.register("parent@example.com", "123456", "OTHERCODE", db_session)

    # AC5: 防止自推荐
    def test_register_raises_on_self_referral(self, db_session):
        """用户不能使用自己生成的邀请码注册"""
        parent = self._make_parent(db_session)
        # parent 生成了自己的邀请码
        ic = self._make_invite_code(db_session, parent.id, "PARENTCODE")
        # parent 尝试用自己生成的邀请码注册（用 parent 的邮箱）
        self._send_register_code(db_session, "parent@example.com")

        service = MockAuthService()
        with pytest.raises(ValueError, match="不能使用自己的邀请码"):
            service.register("parent@example.com", "123456", "PARENTCODE", db_session)

    # M1: 邮箱大小写不能绕过自推荐检查
    def test_register_self_referral_blocked_with_different_case(self, db_session):
        """大小写变体邮箱不能绕过自推荐检查"""
        parent = self._make_parent(db_session, email="Parent@Example.com")
        ic = self._make_invite_code(db_session, parent.id, "PARENTCODE")
        self._send_register_code(db_session, "parent@example.com")

        service = MockAuthService()
        with pytest.raises(ValueError, match="不能使用自己的邀请码"):
            service.register("parent@example.com", "123456", "PARENTCODE", db_session)

    # AC7: 注册后自动生成个人邀请码
    def test_register_auto_generates_personal_invite_code(self, db_session):
        """注册成功后系统自动生成个人邀请码"""
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        user, _ = service.register("new@example.com", "123456", ic.code, db_session)

        # user.invite_code 字段已设置
        assert user.invite_code is not None
        assert len(user.invite_code) > 0

        # invite_codes 表中有对应的记录
        personal_ic = db_session.query(InviteCode).filter(
            InviteCode.code == user.invite_code
        ).first()
        assert personal_ic is not None
        assert personal_ic.generator_id == user.id
        assert personal_ic.used_by is None  # 未使用

    def test_personal_invite_code_has_hmac_format(self, db_session):
        """个人邀请码格式: Base62(user_id).HMAC-SHA256[:16]"""
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session)

        service = MockAuthService()
        user, _ = service.register("new@example.com", "123456", ic.code, db_session)

        # 格式校验: xxx.yyy (Base62 + "." + 16位hex)
        assert "." in user.invite_code
        parts = user.invite_code.split(".")
        assert len(parts) == 2
        assert len(parts[1]) == 16  # HMAC-SHA256[:16]

    def test_personal_invite_code_can_be_used_by_others(self, db_session):
        """自动生成的邀请码可被其他用户使用"""
        # 第一轮: parent 的邀请码 → new_user 注册，自动生成 new_user 的邀请码
        parent = self._make_parent(db_session)
        ic = self._make_invite_code(db_session, parent.id)
        self._send_register_code(db_session, "new@example.com")

        service = MockAuthService()
        user1, _ = service.register("new@example.com", "123456", ic.code, db_session)

        # 第二轮: 另一个用户用 new_user 的邀请码注册
        self._send_register_code(db_session, "another@example.com")
        user2, _ = service.register("another@example.com", "123456", user1.invite_code, db_session)

        assert user2.parent_id == user1.id


class TestEmailAuthService:
    def test_send_email_code_raises_not_implemented(self, db_session):
        service = EmailAuthService()
        with pytest.raises(NotImplementedError):
            service.send_email_code("test@example.com", "login", db_session)

    def test_authenticate_raises_not_implemented(self, db_session):
        service = EmailAuthService()
        with pytest.raises(NotImplementedError):
            service.authenticate("test@example.com", "123456", db_session)

    def test_register_raises_not_implemented(self, db_session):
        service = EmailAuthService()
        with pytest.raises(NotImplementedError):
            service.register("test@example.com", "123456", "CODE", db_session)


class TestGetAuthService:
    def test_returns_mock_service_when_auth_mode_is_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "mock")
        service = get_auth_service()
        assert isinstance(service, MockAuthService)

    def test_returns_email_service_when_auth_mode_is_email(self, monkeypatch):
        monkeypatch.setattr("app.services.auth_service.settings.AUTH_MODE", "email")
        service = get_auth_service()
        assert isinstance(service, EmailAuthService)
