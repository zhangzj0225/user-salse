"""用户管理服务 (Story 4.1)。"""

import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.commission_record import CommissionRecord
from app.models.user import User

logger = logging.getLogger(__name__)


class UserManagementService:
    """管理员用户管理服务。"""

    def list_users(
        self,
        db: Session,
        search: str | None = None,
        role: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """管理员查看用户列表，支持搜索和角色筛选。

        返回: (users, total)
        """
        query = db.query(User)

        if search:
            query = query.filter(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.nickname.ilike(f"%{search}%"),
                )
            )

        if role:
            if role not in ("user", "member", "distributor", "agent"):
                raise ValueError("无效的角色")
            query = query.filter(User.role == role)

        total = query.count()
        users = (
            query.order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # 批量加载 parent_email
        parent_ids = {u.parent_id for u in users if u.parent_id}
        parents = {}
        if parent_ids:
            parent_list = db.query(User).filter(User.id.in_(parent_ids)).all()
            parents = {p.id: p.email for p in parent_list}

        return [
            {
                "id": u.id,
                "email": u.email,
                "nickname": u.nickname,
                "role": u.role,
                "status": u.status,
                "parent_id": u.parent_id,
                "parent_email": parents.get(u.parent_id) if u.parent_id else None,
                "account_quota": u.account_quota,
                "account_used": u.account_used,
                "created_at": u.created_at,
            }
            for u in users
        ], total

    def get_user_detail(self, user_id: int, db: Session) -> dict:
        """查看用户详情：基本信息 + 团队统计 + 收益汇总。"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        # 上级邮箱
        parent_email = None
        if user.parent_id:
            parent = db.query(User).filter(User.id == user.parent_id).first()
            parent_email = parent.email if parent else None

        # 团队统计
        direct_count = db.query(User).filter(User.parent_id == user_id).count()

        # 递归统计所有下级
        total_count = direct_count
        queue = [user_id]
        visited = {user_id}
        while queue:
            current = queue.pop(0)
            children = db.query(User).filter(User.parent_id == current).all()
            for child in children:
                if child.id not in visited:
                    visited.add(child.id)
                    queue.append(child.id)
            if current != user_id:
                pass  # direct_count 已计
        total_count = len(visited) - 1  # 排除自己

        # 收益汇总
        from app.services.earnings_service import calculate_balance_summary
        total_commission, withdrawn, available = calculate_balance_summary(user_id, db)

        return {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role,
            "status": user.status,
            "parent_id": user.parent_id,
            "parent_email": parent_email,
            "account_quota": user.account_quota,
            "account_used": user.account_used,
            "created_at": user.created_at,
            "direct_downline_count": direct_count,
            "total_downline_count": total_count,
            "total_commission": str(total_commission),
            "withdrawn_total": str(withdrawn),
            "available_balance": str(available),
        }


def get_user_management_service() -> UserManagementService:
    return UserManagementService()
