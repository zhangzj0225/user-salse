from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, generate_invite_code
from app.models.admin_user import AdminUser
from app.models.email_verification_code import EmailVerificationCode
from app.models.invite_code import InviteCode
from app.models.user import User

# Dummy bcrypt hash of "dummy" for constant-time comparison when user not found
_DUMMY_HASH = "$2b$12$LJ3m4ys3GZfnYMz8kVsKaekyOsqAVtG2X7VOq8MS3DU8N7rthnfKa"


def _verify_email_code(
    db: Session, email: str, scene: str, code: str
) -> EmailVerificationCode:
    """Verify email verification code from DB. Returns the record if valid, raises ValueError otherwise."""
    record = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.email == email,
            EmailVerificationCode.scene == scene,
            EmailVerificationCode.verified == False,
            EmailVerificationCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    if not record:
        raise ValueError("验证码错误或已过期")
    if code != record.code:
        raise ValueError("验证码错误")
    return record


class AuthService(ABC):
    @abstractmethod
    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        ...

    @abstractmethod
    def authenticate(self, email: str, code: str, db: Session) -> tuple[User, str]:
        """Login flow: find-or-create user without invite code (cold-start / admin seeding).
        Intentional design: allows creating root-level users with no parent_id,
        used for admin-seeded first-batch users before viral distribution begins.
        """
        ...

    @abstractmethod
    def register(self, email: str, code: str, invite_code: str, db: Session) -> tuple[User, str]:
        """Registration flow: invite code required, establishes parent_id for distribution tree."""
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

    def authenticate(self, email: str, code: str, db: Session) -> tuple[User, str]:
        record = _verify_email_code(db, email, "login", code)
        record.verified = True

        # Cold-start / admin seeding: create user without invite code (no parent_id).
        # Normal users enter via /register which requires an invite code.
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, role="user", status="active")
            db.add(user)
            db.flush()

        db.commit()

        token = create_access_token(subject=user.id, role=user.role, token_type="user")
        return user, token

    def register(self, email: str, code: str, invite_code: str, db: Session) -> tuple[User, str]:
        record = _verify_email_code(db, email, "register", code)

        # Check if invite code exists at all (distinct from "already used")
        ic_exists = db.query(InviteCode).filter(InviteCode.code == invite_code).first()
        if not ic_exists:
            raise ValueError("邀请码无效")

        # AC5: 防止自推荐 — 邀请码生成者的邮箱不能与注册邮箱相同
        # 此检查在邮箱查重之前，给出更精确的错误信息
        generator = db.query(User).filter(User.id == ic_exists.generator_id).first()
        if generator and generator.email == email:
            raise ValueError("不能使用自己的邀请码")

        if db.query(User).filter(User.email == email).first():
            raise ValueError("邮箱已注册")

        # Lock the row for update to prevent TOCTOU race
        ic = (
            db.query(InviteCode)
            .filter(InviteCode.code == invite_code, InviteCode.used_by == None)
            .with_for_update()
            .first()
        )
        if not ic:
            raise ValueError("邀请码已被使用")

        now = datetime.now(timezone.utc)
        user = User(email=email, role="user", status="active", parent_id=ic.generator_id)
        db.add(user)
        db.flush()

        # AC7: 自动生成个人邀请码
        personal_code = generate_invite_code(user.id)
        user.invite_code = personal_code
        personal_ic = InviteCode(code=personal_code, generator_id=user.id)
        db.add(personal_ic)

        ic.used_by = user.id
        ic.used_at = now
        record.verified = True

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("邮箱已注册")

        token = create_access_token(subject=user.id, role=user.role, token_type="user")
        return user, token


class EmailAuthService(AuthService):
    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        raise NotImplementedError("Email auth not implemented yet")

    def authenticate(self, email: str, code: str, db: Session) -> tuple[User, str]:
        raise NotImplementedError("Email auth not implemented yet")

    def register(self, email: str, code: str, invite_code: str, db: Session) -> tuple[User, str]:
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
