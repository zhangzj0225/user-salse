"""License 生成与验证服务。

⚠️ 本文件为 Story 3.3 创建的 STUB。实际 License Code 生成逻辑
（HMAC 签名、防篡改）在 Story 3.11 实现。
"""

import logging

from sqlalchemy.orm import Session

from app.models.license import License

logger = logging.getLogger(__name__)


class LicenseService:
    def generate_for_recharge(
        self,
        user_id: int,
        email: str,
        recharge_id: int,
        target_role: str,
        db: Session,
    ) -> License | None:
        """充值确认后生成 License。

        STUB：Story 3.3 仅预留调用点，实际 License 生成在 Story 3.11。
        当前实现仅记录日志，不创建 License 记录。
        """
        # TODO: Story 3.11 — 实现 License Code 生成（HMAC 签名 + 写入 licenses 表）
        # source 映射：888 → "recharge"，5000/10000 → "role_builtin"
        logger.info(
            "License generation stub (Story 3.11 will implement): "
            "user_id=%d recharge_id=%d target_role=%s",
            user_id,
            recharge_id,
            target_role,
        )
        return None


def get_license_service() -> LicenseService:
    return LicenseService()
