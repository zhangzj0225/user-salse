"""可售额度服务。"""

import logging

from sqlalchemy.orm import Session

from app.models.recharge import Recharge
from app.models.user import User

logger = logging.getLogger(__name__)

ELIGIBLE_ROLES = ("agent", "distributor")


class QuotaService:
    """可售额度查询与管理服务。

    角色权限采用双重检查（defense in depth）：
    - API 层返回 403（HTTP 语义）
    - Service 层拒绝非 eligible 角色（保护内部调用方）
    """

    def _get_user(self, user_id: int, db: Session) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")
        if user.role not in ELIGIBLE_ROLES:
            raise ValueError("无权访问额度页面")
        return user

    def get_quota_info(self, user_id: int, db: Session) -> dict:
        """获取用户额度信息。

        返回: {
            "role": str,
            "account_quota": int,
            "account_used": int,
            "remaining": int,
            "can_replenish": bool,
            "sales_records": list[dict],
        }
        """
        user = self._get_user(user_id, db)

        # 已销售记录：该用户作为 parent_id 的已批准充值记录
        # 使用 JOIN 预加载 child_email，避免 N+1 查询
        sales_records = (
            db.query(Recharge, User)
            .join(User, Recharge.user_id == User.id)
            .filter(User.parent_id == user.id, Recharge.status == "approved")
            .order_by(Recharge.created_at.desc())
            .all()
        )

        remaining = user.account_quota - user.account_used

        return {
            "role": user.role,
            "account_quota": user.account_quota,
            "account_used": user.account_used,
            "remaining": remaining,
            "can_replenish": remaining == 0,
            "sales_records": [
                {
                    "recharge_id": r.id,
                    "child_email": u.email,
                    "amount": str(r.amount),
                    "target_role": r.target_role,
                    "approved_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                }
                for r, u in sales_records
            ],
        }

    def check_quota_available(self, user_id: int, needed: int, db: Session) -> bool:
        """检查用户是否有足够额度。"""
        user = self._get_user(user_id, db)
        return user.account_quota - user.account_used >= needed

    def consume_quota(self, user_id: int, amount: int, db: Session) -> None:
        """消耗额度（account_used += amount）。

        使用行锁防止并发超额销售。
        注意：调用方负责 commit。
        """
        # with_for_update 行锁，防止并发超额
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if not user:
            raise ValueError("用户不存在")
        if user.role not in ELIGIBLE_ROLES:
            raise ValueError("无权操作额度")
        if user.account_quota - user.account_used < amount:
            raise ValueError("额度不足")
        user.account_used += amount
        db.flush()
        logger.info(
            "Quota consumed: user_id=%d amount=%d used=%d/%d",
            user_id, amount, user.account_used, user.account_quota,
        )


def get_quota_service() -> QuotaService:
    return QuotaService()
