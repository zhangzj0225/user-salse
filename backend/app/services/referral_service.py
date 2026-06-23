"""推荐码生成与验证服务。"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import generate_invite_code, verify_invite_code_signature
from app.models.referral_code import ReferralCode

logger = logging.getLogger(__name__)


class ReferralService:
    """推荐码生成、验证、查询服务。

    持久码逻辑：每用户1个推荐码，可重复使用，不会标记为已使用。
    """

    def get_or_create_referral_code(self, user_id: int, db: Session) -> ReferralCode:
        """获取或创建用户的持久推荐码。

        每人1个持久码，已存在则返回，不存在则创建。
        只 flush 不 commit，由调用方统一 commit。
        """
        existing = (
            db.query(ReferralCode)
            .filter(ReferralCode.user_id == user_id)
            .first()
        )
        if existing:
            return existing

        code = generate_invite_code(user_id)
        rc = ReferralCode(code=code, user_id=user_id, key_version=1)
        db.add(rc)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise ValueError("推荐码生成冲突，请重试")
        logger.info("Referral code generated: user_id=%d code=%s", user_id, code)
        return rc

    def validate_referral_code(self, code: str, db: Session) -> dict:
        """验证推荐码：签名校验 + 数据库查找。

        返回: {"valid": bool, "user_id": int | None}
        """
        # 1. 签名校验（HMAC）
        valid, sig_user_id = verify_invite_code_signature(code)
        if not valid:
            return {"valid": False, "user_id": None}

        # 2. 数据库查找（确认推荐码确实存在于系统中）
        rc = db.query(ReferralCode).filter(ReferralCode.code == code).first()
        if not rc:
            return {"valid": False, "user_id": None}

        # 交叉验证 — 签名中的 user_id 必须与 DB 中的 user_id 一致
        if sig_user_id != rc.user_id:
            logger.warning(
                "Referral code user_id mismatch: sig_user_id=%d db_user_id=%d code=%s",
                sig_user_id, rc.user_id, code,
            )
            return {"valid": False, "user_id": None}

        # 检查推荐码是否有效（未被停用）
        if not rc.is_active:
            return {"valid": False, "user_id": None}

        return {"valid": True, "user_id": rc.user_id}

    def list_user_codes(self, user_id: int, db: Session) -> list[ReferralCode]:
        """列出用户的推荐码，按创建时间倒序。"""
        return (
            db.query(ReferralCode)
            .filter(ReferralCode.user_id == user_id)
            .order_by(ReferralCode.created_at.desc())
            .all()
        )


def get_referral_service() -> ReferralService:
    return ReferralService()
