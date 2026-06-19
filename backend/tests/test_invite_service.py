"""Tests for app.services.invite_service — 邀请码生成、验证、查询。"""

import pytest

from app.models.invite_code import InviteCode
from app.models.user import User
from app.services.invite_service import InviteCodeService


class TestGenerateForUser:
    def test_generates_and_persists_invite_code(self, db_session):
        user = User(email="test@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        ic = service.generate_for_user(user.id, db_session)

        assert ic.id is not None
        assert ic.code is not None
        assert "." in ic.code
        assert ic.generator_id == user.id
        assert ic.key_version == 1
        assert ic.used_by is None

    def test_user_can_generate_multiple_codes(self, db_session):
        user = User(email="multi@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        ic1 = service.generate_for_user(user.id, db_session)
        ic2 = service.generate_for_user(user.id, db_session)

        # 不同 nonce 生成不同邀请码
        assert ic1.code != ic2.code
        assert ic1.generator_id == ic2.generator_id == user.id

    def test_generate_limits_unused_codes(self, db_session):
        """S2: 超过 10 个未使用邀请码时拒绝生成"""
        user = User(email="limit@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        # 生成 10 个（上限）
        for _ in range(10):
            service.generate_for_user(user.id, db_session)

        # 第 11 个应被拒绝
        import pytest
        with pytest.raises(ValueError, match="已达上限"):
            service.generate_for_user(user.id, db_session)


class TestListUserCodes:
    def test_returns_all_codes_for_user(self, db_session):
        user = User(email="lister@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        service.generate_for_user(user.id, db_session)
        service.generate_for_user(user.id, db_session)

        codes = service.list_user_codes(user.id, db_session)
        assert len(codes) == 2
        assert all(c.generator_id == user.id for c in codes)

    def test_returns_empty_for_user_with_no_codes(self, db_session):
        user = User(email="empty@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        codes = service.list_user_codes(user.id, db_session)
        assert len(codes) == 0

    def test_does_not_return_other_users_codes(self, db_session):
        user1 = User(email="u1@example.com", role="user", status="active")
        user2 = User(email="u2@example.com", role="user", status="active")
        db_session.add_all([user1, user2])
        db_session.flush()

        service = InviteCodeService()
        service.generate_for_user(user1.id, db_session)

        codes = service.list_user_codes(user2.id, db_session)
        assert len(codes) == 0


class TestVerifyCode:
    def test_valid_unused_code(self, db_session):
        user = User(email="valid@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        ic = service.generate_for_user(user.id, db_session)

        result = service.verify_code(ic.code, db_session)
        assert result["valid"] is True
        assert result["generator_id"] == user.id
        assert result["used"] is False

    def test_valid_used_code(self, db_session):
        generator = User(email="gen@example.com", role="agent", status="active")
        receiver = User(email="rec@example.com", role="user", status="active")
        db_session.add_all([generator, receiver])
        db_session.flush()

        service = InviteCodeService()
        ic = service.generate_for_user(generator.id, db_session)

        # 标记为已使用
        ic.used_by = receiver.id
        db_session.flush()

        result = service.verify_code(ic.code, db_session)
        assert result["valid"] is True
        assert result["generator_id"] == generator.id
        assert result["used"] is True

    def test_invalid_format_no_dot(self, db_session):
        service = InviteCodeService()
        result = service.verify_code("invalidcode", db_session)
        assert result["valid"] is False
        assert result["generator_id"] is None
        assert result["used"] is False

    def test_invalid_format_only_one_dot(self, db_session):
        service = InviteCodeService()
        result = service.verify_code("1.abcd", db_session)
        assert result["valid"] is False

    def test_code_not_in_database(self, db_session):
        service = InviteCodeService()
        # 有效签名格式但不在数据库中
        from app.core.security import generate_invite_code
        code = generate_invite_code(999)
        result = service.verify_code(code, db_session)
        assert result["valid"] is False
        assert result["generator_id"] is None

    def test_signature_mismatch(self, db_session):
        """邀请码签名被篡改"""
        user = User(email="tamper@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = InviteCodeService()
        ic = service.generate_for_user(user.id, db_session)

        # 篡改签名部分（替换最后一个段）
        parts = ic.code.split(".")
        tampered_code = f"{parts[0]}.{parts[1]}.0000000000000000"
        result = service.verify_code(tampered_code, db_session)
        assert result["valid"] is False
        assert result["generator_id"] is None
