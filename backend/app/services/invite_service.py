"""邀请码生成与验证服务。"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import generate_invite_code, verify_invite_code_signature
from app.models.invite_code import InviteCode

logger = logging.getLogger(__name__)

# 每用户最多未使用邀请码数量
_MAX_UNUSED_CODES = 10


class InviteCodeService:
    """邀请码生成、验证、查询服务。"""

    def generate_for_user(self, user_id: int, db: Session) -> InviteCode:
        """为用户生成一个新的邀请码并持久化。

        用户可生成多个未使用的邀请码（每次生成包含随机 nonce）。
        S2: 限制每用户最多 _MAX_UNUSED_CODES 个未使用邀请码。
        M1: nonce 碰撞时重试（最多 3 次）。
        """
        # S2: 频率限制 — 检查未使用邀请码数量
        unused_count = (
            db.query(InviteCode)
            .filter(InviteCode.generator_id == user_id, InviteCode.used_by == None)
            .count()
        )
        if unused_count >= _MAX_UNUSED_CODES:
            raise ValueError(f"未使用邀请码已达上限（{_MAX_UNUSED_CODES} 个）")

        # M1: 重试机制应对 nonce 碰撞
        for attempt in range(3):
            code = generate_invite_code(user_id)
            ic = InviteCode(code=code, generator_id=user_id, key_version=1)
            db.add(ic)
            try:
                db.commit()
                db.refresh(ic)
                logger.info("Invite code generated: user_id=%d code=%s", user_id, code)
                return ic
            except IntegrityError:
                db.rollback()
                if attempt < 2:
                    logger.warning(
                        "Invite code collision, retrying: user_id=%d attempt=%d",
                        user_id, attempt + 1,
                    )
                    continue
                raise ValueError("邀请码生成冲突，请重试")

        raise ValueError("邀请码生成冲突，请重试")

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
        # 1. 签名校验（HMAC）— S1: 使用返回的 user_id 做交叉验证
        valid, sig_user_id = verify_invite_code_signature(code)
        if not valid:
            return {"valid": False, "generator_id": None, "used": False}

        # 2. 数据库查找（确认邀请码确实存在于系统中）
        ic = db.query(InviteCode).filter(InviteCode.code == code).first()
        if not ic:
            # 签名有效但不在数据库中（可能已删除或从未生成）
            return {"valid": False, "generator_id": None, "used": False}

        # S1: 交叉验证 — 签名中的 user_id 必须与 DB 中的 generator_id 一致
        if sig_user_id != ic.generator_id:
            logger.warning(
                "Invite code user_id mismatch: sig_user_id=%d db_generator_id=%d code=%s",
                sig_user_id, ic.generator_id, code,
            )
            return {"valid": False, "generator_id": None, "used": False}

        return {
            "valid": True,
            "generator_id": ic.generator_id,
            "used": ic.used_by is not None,
        }


def get_invite_code_service() -> InviteCodeService:
    return InviteCodeService()
