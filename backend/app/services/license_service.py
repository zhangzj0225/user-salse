"""License 生成与验证服务。"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import _base62_decode, _base62_encode
from app.models.license import License

logger = logging.getLogger(__name__)

CURRENT_KEY_VERSION = 1


def _generate_license_code(user_id: int, email: str, nonce: str | None = None) -> str:
    """生成 License Code：Base62(user_id).email_hash[:8].nonce.HMAC[:16]

    格式: {base62_user_id}.{email_hash_8}.{nonce_8}.{hmac_16}
    签名 payload: {user_id}:{email}:{nonce}
    """
    if nonce is None:
        nonce = secrets.token_hex(4)
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:8]
    payload = f"{user_id}:{email}:{nonce}".encode("utf-8")
    secret = settings.LICENSE_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]
    return f"{_base62_encode(user_id)}.{email_hash}.{nonce}.{signature}"


def _verify_license_code(code: str, email: str) -> tuple[bool, int | None]:
    """验证 License Code 签名。

    返回: (valid, user_id)
    """
    parts = code.split(".")
    if len(parts) != 4:
        return (False, None)

    base62_uid, email_hash, nonce, signature = parts
    if not all([base62_uid, email_hash, nonce, signature]):
        return (False, None)

    try:
        user_id = _base62_decode(base62_uid)
    except (ValueError, IndexError):
        return (False, None)

    # 校验 email hash
    expected_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:8]
    if not hmac.compare_digest(email_hash, expected_hash):
        return (False, None)

    # 校验签名
    payload = f"{user_id}:{email}:{nonce}".encode("utf-8")
    secret = settings.LICENSE_SECRET.encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected_sig):
        return (False, None)

    return (True, user_id)


class LicenseService:
    """License 生成与验证服务。"""

    def generate_for_recharge(
        self,
        user_id: int,
        email: str,
        recharge_id: int,
        target_role: str,
        db: Session,
    ) -> License | None:
        """充值确认后生成 License。

        source 映射：888 → "recharge"，5000/10000 → "role_builtin"
        """
        source = "recharge" if target_role == "member" else "role_builtin"

        code = _generate_license_code(user_id, email)
        license_obj = License(
            code=code,
            user_id=user_id,
            email=email,
            source=source,
            source_id=recharge_id,
            status="unused",
            key_version=CURRENT_KEY_VERSION,
        )
        db.add(license_obj)
        db.flush()

        logger.info(
            "License generated: user_id=%d recharge_id=%d role=%s code=%s",
            user_id, recharge_id, target_role, code,
        )
        return license_obj

    def get_user_license(self, user_id: int, db: Session) -> License | None:
        """获取用户最新的 License（供"我的"页面查看）。"""
        return (
            db.query(License)
            .filter(License.user_id == user_id)
            .order_by(License.id.desc())
            .first()
        )

    def verify_and_activate(
        self,
        code: str,
        email: str,
        db: Session,
    ) -> dict:
        """验证并激活 License（供舆情系统调用）。

        验证步骤：
        1. 签名校验（防篡改）
        2. DB 查询 License 是否存在
        3. 邮箱匹配
        4. 状态检查（必须为 unused）
        5. 激活：status → activated, activated_at → now

        返回: {"success": bool, "message": str}
        """
        # 1. 签名校验
        valid, parsed_user_id = _verify_license_code(code, email)
        if not valid:
            return {"success": False, "message": "License 签名验证失败"}

        # 2. DB 查询
        license_obj = db.query(License).filter(License.code == code).first()
        if not license_obj:
            return {"success": False, "message": "License 不存在"}

        # 3. 邮箱匹配
        if license_obj.email != email:
            return {"success": False, "message": "邮箱与 License 不匹配"}

        # 4. 状态检查
        if license_obj.status == "activated":
            return {"success": False, "message": "License 已激活"}
        if license_obj.status == "expired":
            return {"success": False, "message": "License 已过期"}

        # 5. 激活
        license_obj.status = "activated"
        license_obj.activated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "License activated: code=%s user_id=%d email=%s",
            code, license_obj.user_id, email,
        )
        return {"success": True, "message": "License 激活成功"}


def get_license_service() -> LicenseService:
    return LicenseService()
