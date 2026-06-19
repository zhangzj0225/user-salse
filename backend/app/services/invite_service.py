"""邀请码生成与验证服务。"""

import logging

from sqlalchemy.orm import Session

from app.core.security import generate_invite_code, verify_invite_code_signature
from app.models.invite_code import InviteCode
from app.models.user import User

logger = logging.getLogger(__name__)


class InviteCodeService:
    """邀请码生成、验证、查询服务。"""

    def generate_for_user(self, user_id: int, db: Session) -> InviteCode:
        """为用户生成一个新的邀请码并持久化。

        用户可生成多个未使用的邀请码（每次生成包含随机 nonce）。
        """
        code = generate_invite_code(user_id)
        ic = InviteCode(code=code, generator_id=user_id, key_version=1)
        db.add(ic)
        db.commit()
        db.refresh(ic)
        logger.info("Invite code generated: user_id=%d code=%s", user_id, code)
        return ic

    def list_user_codes(self, user_id: int, db: Session) -> list[InviteCode]:
        """列出用户生成的所有邀请码，按创建时间倒序。"""
        return (
            db.query(InviteCode)
            .filter(InviteCode.generator_id == user_id)
            .order_by(InviteCode.created_at.desc())
            .all()
        )

    def verify_code(self, code: str, db: Session) -> dict:
        """验证邀请码：签名校验 + 数据库查找。

        返回: {"valid": bool, "generator_id": int | None, "used": bool}
        """
        # 1. 签名校验（HMAC）
        valid, user_id = verify_invite_code_signature(code)
        if not valid:
            return {"valid": False, "generator_id": None, "used": False}

        # 2. 数据库查找（确认邀请码确实存在于系统中）
        ic = db.query(InviteCode).filter(InviteCode.code == code).first()
        if not ic:
            # 签名有效但不在数据库中（可能已删除或从未生成）
            return {"valid": False, "generator_id": None, "used": False}

        return {
            "valid": True,
            "generator_id": ic.generator_id,
            "used": ic.used_by is not None,
        }


def get_invite_code_service() -> InviteCodeService:
    return InviteCodeService()
