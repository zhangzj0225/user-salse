"""Tests for app.services.referral_service — 推荐码生成、验证、查询。"""

import pytest

from app.models.referral_code import ReferralCode
from app.models.user import User
from app.services.referral_service import ReferralService


class TestGetOrCreateReferralCode:
    def test_creates_new_code_for_user(self, db_session):
        user = User(email="test@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        rc = service.get_or_create_referral_code(user.id, db_session)

        assert rc.id is not None
        assert rc.code is not None
        assert "." in rc.code
        assert rc.user_id == user.id
        assert rc.key_version == 1
        assert rc.is_active == 1

    def test_returns_existing_code_for_same_user(self, db_session):
        """每人1个持久码，重复调用返回同一个。"""
        user = User(email="multi@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        rc1 = service.get_or_create_referral_code(user.id, db_session)
        rc2 = service.get_or_create_referral_code(user.id, db_session)

        assert rc1.id == rc2.id
        assert rc1.code == rc2.code
        assert rc1.user_id == rc2.user_id == user.id


class TestListUserCodes:
    def test_returns_codes_for_user(self, db_session):
        user = User(email="lister@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        service.get_or_create_referral_code(user.id, db_session)

        codes = service.list_user_codes(user.id, db_session)
        assert len(codes) == 1
        assert all(c.user_id == user.id for c in codes)

    def test_returns_empty_for_user_with_no_codes(self, db_session):
        user = User(email="empty@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        codes = service.list_user_codes(user.id, db_session)
        assert len(codes) == 0

    def test_does_not_return_other_users_codes(self, db_session):
        user1 = User(email="u1@example.com", role="distributor", status="active")
        user2 = User(email="u2@example.com", role="distributor", status="active")
        db_session.add_all([user1, user2])
        db_session.flush()

        service = ReferralService()
        service.get_or_create_referral_code(user1.id, db_session)

        codes = service.list_user_codes(user2.id, db_session)
        assert len(codes) == 0


class TestValidateReferralCode:
    def test_valid_active_code(self, db_session):
        user = User(email="valid@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        rc = service.get_or_create_referral_code(user.id, db_session)

        result = service.validate_referral_code(rc.code, db_session)
        assert result["valid"] is True
        assert result["user_id"] == user.id

    def test_invalid_format_no_dot(self, db_session):
        service = ReferralService()
        result = service.validate_referral_code("invalidcode", db_session)
        assert result["valid"] is False
        assert result["user_id"] is None

    def test_invalid_format_only_one_dot(self, db_session):
        service = ReferralService()
        result = service.validate_referral_code("1.abcd", db_session)
        assert result["valid"] is False

    def test_code_not_in_database(self, db_session):
        service = ReferralService()
        from app.core.security import generate_invite_code
        code = generate_invite_code(999)
        result = service.validate_referral_code(code, db_session)
        assert result["valid"] is False
        assert result["user_id"] is None

    def test_signature_mismatch(self, db_session):
        """推荐码签名被篡改"""
        user = User(email="tamper@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        rc = service.get_or_create_referral_code(user.id, db_session)

        # 篡改签名部分（替换最后一个段）
        parts = rc.code.split(".")
        tampered_code = f"{parts[0]}.{parts[1]}.0000000000000000"
        result = service.validate_referral_code(tampered_code, db_session)
        assert result["valid"] is False
        assert result["user_id"] is None

    def test_inactive_code_is_invalid(self, db_session):
        """已停用的推荐码验证失败"""
        user = User(email="inactive@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.flush()

        service = ReferralService()
        rc = service.get_or_create_referral_code(user.id, db_session)

        # 停用推荐码
        rc.is_active = 0
        db_session.flush()

        result = service.validate_referral_code(rc.code, db_session)
        assert result["valid"] is False
        assert result["user_id"] is None
