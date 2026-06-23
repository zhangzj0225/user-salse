"""Tests for app.core.security — JWT token creation, decoding, and get_current_user."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_invite_code,
    get_current_user,
    verify_invite_code_signature,
)
from app.models.user import User


class TestCreateAccessToken:
    def test_returns_valid_jwt_string(self):
        token = create_access_token(subject=1, role="distributor", token_type="user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_all_required_claims(self):
        token = create_access_token(subject=42, role="agent", token_type="user")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["role"] == "agent"
        assert payload["type"] == "user"
        assert "iat" in payload
        assert "exp" in payload

    def test_exp_is_in_the_future(self):
        token = create_access_token(subject=1, role="distributor", token_type="user")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        now = int(datetime.now(timezone.utc).timestamp())
        assert payload["exp"] > now

    def test_iat_is_close_to_now(self):
        token = create_access_token(subject=1, role="distributor", token_type="user")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        now = int(datetime.now(timezone.utc).timestamp())
        assert abs(payload["iat"] - now) < 5


class TestDecodeAccessToken:
    def test_decodes_valid_token(self):
        token = create_access_token(subject=1, role="distributor", token_type="user")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"

    def test_raises_value_error_on_expired_token(self):
        now = datetime.now(timezone.utc)
        expire = now - timedelta(hours=1)
        payload = {"sub": 1, "role": "distributor", "type": "user", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(expired_token)

    def test_raises_value_error_on_tampered_token(self):
        token = create_access_token(subject=1, role="distributor", token_type="user")
        parts = token.rsplit(".", 1)
        tampered = parts[0][:-1] + ("A" if parts[0][-1] != "A" else "B") + "." + parts[1]
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(tampered)

    def test_raises_value_error_on_wrong_secret(self):
        payload = {"sub": 1, "role": "distributor", "type": "user", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(token)

    def test_raises_value_error_on_missing_required_claim(self):
        now = datetime.now(timezone.utc)
        payload = {"sub": 1, "role": "distributor", "iat": now, "exp": now + timedelta(hours=1)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(token)

    def test_raises_value_error_on_garbage_string(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not-a-valid-jwt")


class TestGetCurrentUser:
    def test_returns_user_when_token_valid_and_user_exists(self, db_session):
        user = User(email="test@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user(credentials=credentials, db=db_session)
        assert result.id == user.id

    def test_raises_401_when_user_not_found(self, db_session):
        token = create_access_token(subject=99999, role="distributor", token_type="user")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=credentials, db=db_session)
        assert exc.value.status_code == 401

    def test_raises_401_when_token_expired(self, db_session):
        now = datetime.now(timezone.utc)
        expire = now - timedelta(hours=1)
        payload = {"sub": 1, "role": "distributor", "type": "user", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=credentials, db=db_session)
        assert exc.value.status_code == 401

    def test_raises_401_when_token_invalid(self, db_session):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="garbage")
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=credentials, db=db_session)
        assert exc.value.status_code == 401


class TestGenerateReferralCode:
    """S2: generate_invite_code 直接单元测试"""

    def test_different_invocations_different_codes(self):
        """每次调用生成不同邀请码（随机 nonce）"""
        code1 = generate_invite_code(42)
        code2 = generate_invite_code(42)
        assert code1 != code2

    def test_different_user_ids_different_codes(self):
        """不同 user_id 生成不同邀请码"""
        code1 = generate_invite_code(1)
        code2 = generate_invite_code(2)
        assert code1 != code2

    def test_format_contains_two_dot_separators(self):
        """格式: Base62(user_id).nonce.HMAC-SHA256[:16]"""
        code = generate_invite_code(100)
        parts = code.split(".")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # nonce = 4 bytes = 8 hex chars
        assert len(parts[2]) == 16  # 16 hex chars = 64 bits

    def test_base62_encoding(self):
        """Base62 编码正确性"""
        # user_id=0 → "0"
        code0 = generate_invite_code(0)
        assert code0.startswith("0.")

        # user_id=62 → "10" (62 in base62)
        code62 = generate_invite_code(62)
        assert code62.startswith("10.")

        # user_id=1 → "1"
        code1 = generate_invite_code(1)
        assert code1.startswith("1.")

    def test_hmac_signature_verifiable(self):
        """HMAC 签名可通过 verify_invite_code_signature 验证"""
        user_id = 123
        code = generate_invite_code(user_id)

        valid, extracted_uid = verify_invite_code_signature(code)
        assert valid is True
        assert extracted_uid == user_id

    def test_verify_rejects_tampered_signature(self):
        """篡改签名后验证失败"""
        code = generate_invite_code(42)
        parts = code.split(".")
        tampered = f"{parts[0]}.{parts[1]}.ffffffffffffffff"

        valid, uid = verify_invite_code_signature(tampered)
        assert valid is False
        assert uid is None

    def test_verify_rejects_wrong_format(self):
        """格式错误验证失败"""
        valid, uid = verify_invite_code_signature("no-dots-here")
        assert valid is False
        assert uid is None

        valid2, uid2 = verify_invite_code_signature("1.onlyonedot")
        assert valid2 is False
        assert uid2 is None
