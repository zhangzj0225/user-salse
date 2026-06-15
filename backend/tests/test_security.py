"""Tests for app.core.security — JWT token creation, decoding, and get_current_user."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, get_current_user
from app.models.user import User


class TestCreateAccessToken:
    def test_returns_valid_jwt_string(self):
        token = create_access_token(subject=1, role="user", token_type="wechat")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_all_required_claims(self):
        token = create_access_token(subject=42, role="agent", token_type="wechat")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["role"] == "agent"
        assert payload["type"] == "wechat"
        assert "iat" in payload
        assert "exp" in payload

    def test_exp_is_in_the_future(self):
        token = create_access_token(subject=1, role="user", token_type="wechat")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        now = int(datetime.now(timezone.utc).timestamp())
        assert payload["exp"] > now

    def test_iat_is_close_to_now(self):
        token = create_access_token(subject=1, role="user", token_type="wechat")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        now = int(datetime.now(timezone.utc).timestamp())
        assert abs(payload["iat"] - now) < 5


class TestDecodeAccessToken:
    def test_decodes_valid_token(self):
        token = create_access_token(subject=1, role="user", token_type="wechat")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"

    def test_raises_value_error_on_expired_token(self):
        # Create a token that expired 1 hour ago
        now = datetime.now(timezone.utc)
        expire = now - timedelta(hours=1)
        payload = {"sub": 1, "role": "user", "type": "wechat", "iat": now, "exp": expire}
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(expired_token)

    def test_raises_value_error_on_tampered_token(self):
        token = create_access_token(subject=1, role="user", token_type="wechat")
        # Tamper with the token by changing the last character of the payload
        parts = token.rsplit(".", 1)
        tampered = parts[0][:-1] + ("A" if parts[0][-1] != "A" else "B") + "." + parts[1]
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(tampered)

    def test_raises_value_error_on_wrong_secret(self):
        payload = {"sub": 1, "role": "user", "type": "wechat", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(token)

    def test_raises_value_error_on_missing_required_claim(self):
        now = datetime.now(timezone.utc)
        payload = {"sub": 1, "role": "user", "iat": now, "exp": now + timedelta(hours=1)}
        # Missing "type" claim
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(token)

    def test_raises_value_error_on_garbage_string(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not-a-valid-jwt")


class TestGetCurrentUser:
    def test_returns_user_when_token_valid_and_user_exists(self, db_session):
        user = User(openid="test_openid", phone="13800138000", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="wechat")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user(credentials=credentials, db=db_session)
        assert result.id == user.id

    def test_raises_401_when_user_not_found(self, db_session):
        token = create_access_token(subject=99999, role="user", token_type="wechat")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=credentials, db=db_session)
        assert exc.value.status_code == 401

    def test_raises_401_when_token_expired(self, db_session):
        now = datetime.now(timezone.utc)
        expire = now - timedelta(hours=1)
        payload = {"sub": 1, "role": "user", "type": "wechat", "iat": now, "exp": expire}
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
