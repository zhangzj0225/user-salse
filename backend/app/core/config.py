import logging
from typing import Literal

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# 硬编码默认值，启动校验时若生产环境仍用这些值则拒绝启动（SEC-1）
_DEFAULT_SECRET_KEY = "change-me-in-production"
_DEFAULT_INVITE_SECRET = "invite-secret-change-me"
_DEFAULT_LICENSE_SECRET = "license-secret-change-me"
_DEFAULT_LICENSE_API_KEY = "license-api-key-change-me"
_DEFAULT_PAYMENT_CALLBACK_SECRET = "payment-callback-secret-change-me"


class Settings(BaseSettings):
    AUTH_MODE: Literal["mock", "email"] = "mock"
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/user_salse"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    INVITE_CODE_SECRET: str = _DEFAULT_INVITE_SECRET
    LICENSE_SECRET: str = _DEFAULT_LICENSE_SECRET
    LICENSE_API_KEY: str = _DEFAULT_LICENSE_API_KEY
    # 支付回调 HMAC-SHA256 共享密钥（与 LICENSE_API_KEY 语义不同，应独立配置）
    PAYMENT_CALLBACK_SECRET: str = _DEFAULT_PAYMENT_CALLBACK_SECRET
    # 运行环境：默认 production（fail-closed），生产忘设 ENV 也会强校验密钥。
    # 仅显式设 ENV=dev 时放宽（本地开发/测试）。
    ENV: Literal["dev", "production"] = "production"
    # CORS 允许的来源，逗号分隔。默认 "*"（开发），生产通过 .env 设具体域名。
    CORS_ORIGINS: str = "*"

    # SMTP 邮件配置（AUTH_MODE=email 时必需）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = ""
    # 邮件验证码有效期（分钟）
    EMAIL_CODE_EXPIRE_MINUTES: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()


def validate_security_secrets() -> None:
    """SEC-1: 生产环境启动时校验密钥非默认值。

    生产环境若仍用硬编码默认 secret，签发的 JWT/邀请码/License 可被任何知道
    默认值的人伪造。dev 环境放宽（仅警告）。
    """
    insecure = []
    if settings.SECRET_KEY == _DEFAULT_SECRET_KEY:
        insecure.append("SECRET_KEY")
    if settings.INVITE_CODE_SECRET == _DEFAULT_INVITE_SECRET:
        insecure.append("INVITE_CODE_SECRET")
    if settings.LICENSE_SECRET == _DEFAULT_LICENSE_SECRET:
        insecure.append("LICENSE_SECRET")
    if settings.LICENSE_API_KEY == _DEFAULT_LICENSE_API_KEY:
        insecure.append("LICENSE_API_KEY")
    if settings.PAYMENT_CALLBACK_SECRET == _DEFAULT_PAYMENT_CALLBACK_SECRET:
        insecure.append("PAYMENT_CALLBACK_SECRET")

    if not insecure:
        return

    msg = f"生产环境使用默认密钥: {insecure}，请在 .env 中配置安全值"
    if settings.ENV == "production":
        raise RuntimeError(msg)
    logger.warning("WARNING: %s", msg)


def validate_auth_mode() -> None:
    """SEC-2: 生产环境禁止使用 mock 认证。

    mock 模式下验证码固定为 123456，任何人可登录任意邮箱。
    生产环境必须设 AUTH_MODE=email 并配置 SMTP。
    """
    if settings.AUTH_MODE != "mock":
        return

    msg = "生产环境禁止使用 AUTH_MODE=mock（验证码固定 123456），请设 AUTH_MODE=email 并配置 SMTP"
    if settings.ENV == "production":
        raise RuntimeError(msg)
    logger.warning("WARNING: %s", msg)
