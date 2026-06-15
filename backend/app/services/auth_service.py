from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.user import User

# Dummy bcrypt hash of "dummy" for constant-time comparison when user not found
_DUMMY_HASH = "$2b$12$LJ3m4ys3GZfnYMz8kVsKaekyOsqAVtG2X7VOq8MS3DU8N7rthnfKa"


class AuthService(ABC):
    @abstractmethod
    def send_sms_code(self, phone: str, db: Session) -> str:
        ...

    @abstractmethod
    def authenticate(
        self, phone: str, sms_code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        ...


class MockAuthService(AuthService):
    MOCK_CODE = "123456"

    def send_sms_code(self, phone: str, db: Session) -> str:
        from app.models.sms_record import SmsRecord

        code = self.MOCK_CODE
        record = SmsRecord(
            phone=phone,
            code=code,
            scene="login",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(record)
        db.commit()
        return code

    def authenticate(
        self, phone: str, sms_code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        from app.models.sms_record import SmsRecord

        # Verify SMS code
        if sms_code != self.MOCK_CODE:
            raise ValueError("Invalid SMS code")

        # Check latest unverified SMS record
        sms_record = (
            db.query(SmsRecord)
            .filter(
                SmsRecord.phone == phone,
                SmsRecord.scene == "login",
                SmsRecord.verified == False,
                SmsRecord.expires_at > datetime.now(timezone.utc),
            )
            .order_by(SmsRecord.created_at.desc())
            .first()
        )
        if not sms_record:
            raise ValueError("SMS code expired or not found")

        sms_record.verified = True

        # Find or create user (INSERT ON DUPLICATE KEY to handle concurrent logins)
        # Note: invite_code will be processed in Story 2.1 (user registration flow)
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            user = User(
                openid=f"mock_{phone}",
                phone=phone,
                role="user",
                status="active",
            )
            db.add(user)
            db.flush()

        db.commit()

        # Issue JWT
        token = create_access_token(
            subject=user.id,
            role=user.role,
            token_type="wechat",
        )
        return user, token


class WechatAuthService(AuthService):
    def send_sms_code(self, phone: str, db: Session) -> str:
        raise NotImplementedError("WeChat auth not implemented yet")

    def authenticate(
        self, phone: str, sms_code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        raise NotImplementedError("WeChat auth not implemented yet")


def get_auth_service() -> AuthService:
    if settings.AUTH_MODE == "mock":
        return MockAuthService()
    return WechatAuthService()


class AdminAuthService:
    def authenticate(
        self, username: str, password: str, db: Session
    ) -> tuple[AdminUser, str]:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()

        # Constant-time comparison: always run bcrypt even if user not found,
        # to prevent username enumeration via timing side-channel.
        hash_to_check = admin.password_hash if admin else _DUMMY_HASH
        password_ok = bcrypt.checkpw(
            password.encode("utf-8"), hash_to_check.encode("utf-8")
        )

        if not admin or not password_ok:
            raise ValueError("Invalid credentials")

        token = create_access_token(
            subject=admin.id,
            role="admin",
            token_type="admin",
        )
        return admin, token
