from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User

# Dummy bcrypt hash of "dummy" for constant-time comparison when user not found
_DUMMY_HASH = "$2b$12$LJ3m4ys3GZfnYMz8kVsKaekyOsqAVtG2X7VOq8MS3DU8N7rthnfKa"


class AuthService(ABC):
    @abstractmethod
    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        ...

    @abstractmethod
    def authenticate(
        self, email: str, code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        ...


class MockAuthService(AuthService):
    MOCK_CODE = "123456"

    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        code = self.MOCK_CODE
        record = EmailVerificationCode(
            email=email,
            code=code,
            scene=scene,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(record)
        db.commit()
        return code

    def authenticate(
        self, email: str, code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        # Verify email code
        if code != self.MOCK_CODE:
            raise ValueError("Invalid verification code")

        # Check latest unverified email code
        record = (
            db.query(EmailVerificationCode)
            .filter(
                EmailVerificationCode.email == email,
                EmailVerificationCode.scene == "login",
                EmailVerificationCode.verified == False,
                EmailVerificationCode.expires_at > datetime.now(timezone.utc),
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .first()
        )
        if not record:
            raise ValueError("Verification code expired or not found")

        record.verified = True

        # Find or create user
        # Note: invite_code will be processed in Story 3.1 (user registration flow)
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
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
            token_type="user",
        )
        return user, token


class EmailAuthService(AuthService):
    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        raise NotImplementedError("Email auth not implemented yet")

    def authenticate(
        self, email: str, code: str, invite_code: str | None, db: Session
    ) -> tuple[User, str]:
        raise NotImplementedError("Email auth not implemented yet")


def get_auth_service() -> AuthService:
    if settings.AUTH_MODE == "mock":
        return MockAuthService()
    return EmailAuthService()


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
