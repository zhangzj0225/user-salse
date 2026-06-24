from abc import ABC, abstractmethod
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User

logger = logging.getLogger(__name__)

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
        """Login flow: verify existing user only."""
        ...


class MockAuthService(AuthService):
    MOCK_CODE = "123456"

    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        # M1: 邮箱统一小写化
        email = email.strip().lower()
        # PRD v2 FR-1: 仅已存在用户可登录，不存在则提示"用户不存在"
        if scene == "login":
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise ValueError("用户不存在")
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
        # M1: 邮箱统一小写化
        email = email.strip().lower()
        record = _verify_email_code(db, email, "login", code)
        record.verified = True

        # PRD v2 FR-1: 登录仅认证已存在用户，不创建新用户。
        # 用户创建的唯一路径：(1) 超管创建种子用户 (2) 在线支付 5000/10000。
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("用户不存在")

        db.commit()

        token = create_access_token(subject=user.id, role=user.role, token_type="user")
        return user, token


class EmailAuthService(AuthService):
    """真实邮箱认证服务 — 通过 SMTP 发送验证码。

    与 MockAuthService 的区别仅在 send_email_code：真实发送邮件而非固定 123456。
    authenticate 逻辑完全复用（验码、建用户、发 token）。
    """

    def _send_email_smtp(self, to_email: str, code: str, scene: str) -> None:
        """通过 SMTP 发送验证码邮件。

        scene 用于选择邮件文案：login/sale_verify。
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        scene_text = {
            "login": "登录",
            "sale_verify": "销售验证",
        }.get(scene, "验证")

        subject = f"足球舆情系统 - {scene_text}验证码"
        body = f"""
您的{scene_text}验证码是：{code}

验证码有效期为 {settings.EMAIL_CODE_EXPIRE_MINUTES} 分钟，请尽快使用。
如非本人操作，请忽略此邮件。

— 足球舆情系统
""".strip()

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # 465 端口用 SMTP_SSL（QQ 邮箱等），587/其他端口用 STARTTLS
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())

        logger.info("验证码邮件已发送: to=%s scene=%s", to_email, scene)

    def send_email_code(self, email: str, scene: str, db: Session) -> str:
        # M1: 邮箱统一小写化
        email = email.strip().lower()

        # PRD v2 FR-1: 仅已存在用户可登录，不存在则提示"用户不存在"
        if scene == "login":
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise ValueError("用户不存在")

        # 生成 6 位随机数字验证码
        import secrets
        code = "".join(secrets.choice("0123456789") for _ in range(6))

        # 写入 DB
        record = EmailVerificationCode(
            email=email,
            code=code,
            scene=scene,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES),
        )
        db.add(record)
        db.flush()

        # 通过 SMTP 发送真实邮件（在 commit 前，失败时回滚）
        try:
            self._send_email_smtp(email, code, scene)
        except Exception:
            db.rollback()
            raise
        db.commit()

        return code

    def authenticate(self, email: str, code: str, db: Session) -> tuple[User, str]:
        # M1: 邮箱统一小写化
        email = email.strip().lower()
        record = _verify_email_code(db, email, "login", code)
        record.verified = True

        # PRD v2 FR-1: 登录仅认证已存在用户，不创建新用户。
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("用户不存在")

        db.commit()

        token = create_access_token(subject=user.id, role=user.role, token_type="user")
        return user, token


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
