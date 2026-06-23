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


def _generate_license_code(user_id: int | None, nonce: str | None = None) -> str:
    """生成 License Code：Base62(user_id).nonce.HMAC[:16]

    格式: {base62_user_id}.{nonce_8}.{hmac_16}
    签名 payload: {user_id}:{nonce}
    user_id 为 None 时使用 0 作为占位符（888 支付生成的 License 不关联用户）。
    """
    if nonce is None:
        nonce = secrets.token_hex(4)
    uid = user_id if user_id is not None else 0
    payload = f"{uid}:{nonce}".encode("utf-8")
    secret = settings.LICENSE_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]
    return f"{_base62_encode(uid)}.{nonce}.{signature}"


def _verify_license_code(code: str) -> tuple[bool, int | None]:
    """验证 License Code 签名。

    返回: (valid, user_id)
    user_id 为 0 时返回 None（表示未关联用户）。
    """
    parts = code.split(".")
    if len(parts) != 3:
        return (False, None)

    base62_uid, nonce, signature = parts
    if not all([base62_uid, nonce, signature]):
        return (False, None)

    try:
        user_id = _base62_decode(base62_uid)
    except (ValueError, IndexError):
        return (False, None)

    # 校验签名
    payload = f"{user_id}:{nonce}".encode("utf-8")
    secret = settings.LICENSE_SECRET.encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected_sig):
        return (False, None)

    return (True, user_id if user_id != 0 else None)


class LicenseService:
    """License 生成与验证服务。

    不绑定邮箱：License 通过签名验证，激活时记录业务用户信息。
    """

    def generate_for_payment(
        self,
        user_id: int | None,
        payment_id: int,
        target_role: str,
        db: Session,
    ) -> License | None:
        """支付确认后生成 License。

        source 统一为 "payment"。
        user_id 为 None 时（888 支付），License 不关联用户。
        """
        code = _generate_license_code(user_id)
        license_obj = License(
            code=code,
            user_id=user_id,
            source="payment",
            source_id=payment_id,
            status="unused",
            key_version=CURRENT_KEY_VERSION,
        )
        db.add(license_obj)
        db.flush()

        logger.info(
            "License generated: user_id=%s payment_id=%d role=%s code_prefix=%s",
            user_id, payment_id, target_role, code[:8],
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

    def verify_license(self, code: str, db: Session) -> dict:
        """验证 License：签名校验 + DB 查找 + 状态检查。

        不验证邮箱，不激活。
        返回: {"valid": bool, "message": str, "user_id": int | None}
        """
        # 1. 签名校验
        valid, parsed_user_id = _verify_license_code(code)
        if not valid:
            return {"valid": False, "message": "License 签名验证失败", "user_id": None}

        # 2. DB 查找
        license_obj = db.query(License).filter(License.code == code).first()
        if not license_obj:
            return {"valid": False, "message": "License 不存在", "user_id": None}

        # 3. 状态检查（必须为 unused）
        if license_obj.status == "activated":
            return {"valid": False, "message": "License 已激活", "user_id": None}
        if license_obj.status == "expired":
            return {"valid": False, "message": "License 已过期", "user_id": None}

        return {"valid": True, "message": "License 有效", "user_id": license_obj.user_id}

    def activate_license(
        self,
        code: str,
        business_user_id: str,
        business_user_info: str | None,
        db: Session,
    ) -> dict:
        """激活 License（供舆情系统调用）。

        验证步骤：
        1. 签名校验（防篡改）
        2. DB 查找 License 是否存在（行锁防并发重复激活）
        3. 状态检查（必须为 unused）
        4. 激活：status → activated, activated_user_id, activated_user_info, activated_at

        返回: {"success": bool, "message": str}
        """
        # 1. 签名校验
        valid, _ = _verify_license_code(code)
        if not valid:
            return {"success": False, "message": "License 签名验证失败"}

        # 2. DB 查找（行锁防并发）
        license_obj = (
            db.query(License)
            .filter(License.code == code)
            .with_for_update()
            .first()
        )
        if not license_obj:
            return {"success": False, "message": "License 不存在"}

        # 3. 状态检查
        if license_obj.status == "activated":
            return {"success": False, "message": "License 已激活"}
        if license_obj.status == "expired":
            return {"success": False, "message": "License 已过期"}

        # 4. 激活
        license_obj.status = "activated"
        license_obj.activated_user_id = business_user_id
        license_obj.activated_user_info = business_user_info
        license_obj.activated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "License activated: code_prefix=%s business_user_id=%s",
            code[:8], business_user_id,
        )
        return {"success": True, "message": "License 激活成功"}


def get_license_service() -> LicenseService:
    return LicenseService()
