"""Tests for app.services.license_service — License 生成与验证。"""

import pytest
from app.models.license import License
from app.models.user import User
from app.services.license_service import (
    LicenseService,
    _generate_license_code,
    _verify_license_code,
)


def _make_user(db, email="user@example.com", role="member"):
    u = User(email=email, role=role, status="active")
    db.add(u)
    db.flush()
    return u


class TestGenerateLicenseCode:
    def test_code_format(self):
        """License Code 格式: Base62(uid).email_hash8.nonce8.hmac16"""
        code = _generate_license_code(1, "user@example.com", nonce="abcd1234")
        parts = code.split(".")
        assert len(parts) == 4
        assert parts[0] == "1"  # Base62(1) = "1"
        assert len(parts[1]) == 8  # email_hash
        assert parts[2] == "abcd1234"  # nonce
        assert len(parts[3]) == 16  # hmac

    def test_code_random_nonce(self):
        """不传 nonce 时随机生成"""
        code1 = _generate_license_code(1, "user@example.com")
        code2 = _generate_license_code(1, "user@example.com")
        assert code1 != code2  # nonce 不同

    def test_code_deterministic_with_nonce(self):
        """相同参数生成相同 code"""
        code1 = _generate_license_code(1, "user@example.com", nonce="abcd1234")
        code2 = _generate_license_code(1, "user@example.com", nonce="abcd1234")
        assert code1 == code2


class TestVerifyLicenseCode:
    def test_valid_code(self):
        """有效签名验证通过"""
        code = _generate_license_code(42, "user@example.com", nonce="abcd1234")
        valid, user_id = _verify_license_code(code, "user@example.com")
        assert valid is True
        assert user_id == 42

    def test_tampered_signature(self):
        """篡改签名 → 验证失败"""
        code = _generate_license_code(1, "user@example.com", nonce="abcd1234")
        parts = code.split(".")
        tampered = ".".join([parts[0], parts[1], parts[2], "0" * 16])
        valid, _ = _verify_license_code(tampered, "user@example.com")
        assert valid is False

    def test_wrong_email(self):
        """邮箱不匹配 → 验证失败"""
        code = _generate_license_code(1, "user@example.com", nonce="abcd1234")
        valid, _ = _verify_license_code(code, "wrong@example.com")
        assert valid is False

    def test_malformed_code(self):
        """格式错误 → 验证失败"""
        valid, _ = _verify_license_code("invalid", "user@example.com")
        assert valid is False

    def test_empty_parts(self):
        """空段 → 验证失败"""
        valid, _ = _verify_license_code("...abcd1234deadbeef", "user@example.com")
        assert valid is False


class TestGenerateForRecharge:
    def test_generate_member_license(self, db_session):
        """888 会员充值 → source=recharge"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user_id=user.id,
            email="user@example.com",
            recharge_id=1,
            target_role="member",
            db=db_session,
        )
        assert license_obj is not None
        assert license_obj.source == "recharge"
        assert license_obj.status == "unused"
        assert license_obj.email == "user@example.com"
        assert license_obj.user_id == user.id

    def test_generate_distributor_license(self, db_session):
        """经销商充值 → source=role_builtin"""
        user = _make_user(db_session, "dist@example.com", "distributor")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user_id=user.id,
            email="dist@example.com",
            recharge_id=2,
            target_role="distributor",
            db=db_session,
        )
        assert license_obj.source == "role_builtin"

    def test_generate_agent_license(self, db_session):
        """代理充值 → source=role_builtin"""
        user = _make_user(db_session, "agent@example.com", "agent")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user_id=user.id,
            email="agent@example.com",
            recharge_id=3,
            target_role="agent",
            db=db_session,
        )
        assert license_obj.source == "role_builtin"


class TestGetUserLicense:
    def test_returns_latest(self, db_session):
        """返回最新的 License"""
        user = _make_user(db_session)
        service = LicenseService()
        service.generate_for_recharge(user.id, user.email, 1, "member", db_session)
        service.generate_for_recharge(user.id, user.email, 2, "distributor", db_session)

        license_obj = service.get_user_license(user.id, db_session)
        assert license_obj is not None
        assert license_obj.source_id == 2  # 最新的

    def test_no_license(self, db_session):
        """无 License → None"""
        user = _make_user(db_session)
        service = LicenseService()
        assert service.get_user_license(user.id, db_session) is None


class TestVerifyAndActivate:
    def test_activate_success(self, db_session):
        """正常激活流程"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user.id, "user@example.com", 1, "member", db_session
        )

        result = service.verify_and_activate(license_obj.code, "user@example.com", db_session)
        assert result["success"] is True

        db_session.refresh(license_obj)
        assert license_obj.status == "activated"
        assert license_obj.activated_at is not None

    def test_activate_already_activated(self, db_session):
        """重复激活 → 失败"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user.id, "user@example.com", 1, "member", db_session
        )
        service.verify_and_activate(license_obj.code, "user@example.com", db_session)

        result = service.verify_and_activate(license_obj.code, "user@example.com", db_session)
        assert result["success"] is False
        assert "已激活" in result["message"]

    def test_activate_wrong_email(self, db_session):
        """邮箱不匹配 → 失败"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user.id, "user@example.com", 1, "member", db_session
        )

        result = service.verify_and_activate(license_obj.code, "wrong@example.com", db_session)
        assert result["success"] is False
        assert "签名验证失败" in result["message"]

    def test_activate_expired(self, db_session):
        """已过期 → 失败"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        license_obj = service.generate_for_recharge(
            user.id, "user@example.com", 1, "member", db_session
        )
        license_obj.status = "expired"
        db_session.flush()

        result = service.verify_and_activate(license_obj.code, "user@example.com", db_session)
        assert result["success"] is False
        assert "已过期" in result["message"]

    def test_activate_nonexistent(self, db_session):
        """License 不存在 → 失败"""
        code = _generate_license_code(999, "ghost@example.com", nonce="abcd1234")
        service = LicenseService()
        result = service.verify_and_activate(code, "ghost@example.com", db_session)
        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_activate_tampered_code(self, db_session):
        """篡改的 code → 签名验证失败"""
        user = _make_user(db_session, "user@example.com", "member")
        service = LicenseService()
        service.generate_for_recharge(user.id, "user@example.com", 1, "member", db_session)

        result = service.verify_and_activate("1.aaaaaaaa.abcd1234.0000000000000000", "user@example.com", db_session)
        assert result["success"] is False
        assert "签名验证失败" in result["message"]
