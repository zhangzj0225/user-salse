"""运营数据看板服务 (Story 4.3)。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.recharge import Recharge
from app.models.ticket import Ticket
from app.models.user import User

logger = logging.getLogger(__name__)


class DashboardService:
    """运营数据看板服务。"""

    def get_stats(self, db: Session) -> dict:
        """获取运营看板统计数据。"""
        # 用户统计
        total_users = db.query(User).count()
        agent_count = db.query(User).filter(User.role == "agent").count()
        distributor_count = db.query(User).filter(User.role == "distributor").count()
        member_count = db.query(User).filter(User.role == "member").count()
        regular_user_count = db.query(User).filter(User.role == "user").count()

        # 今日数据 — 使用 func.date() 跨数据库兼容
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_new_users = db.query(User).filter(
            func.date(User.created_at) == today_str
        ).count()

        today_recharge_result = db.query(
            func.coalesce(func.sum(Recharge.amount), 0)
        ).filter(
            func.date(Recharge.created_at) == today_str,
            Recharge.status == "approved",
        ).scalar()
        today_recharge_total = str(Decimal(today_recharge_result))

        # 工单统计
        pending_ticket_count = db.query(Ticket).filter(
            Ticket.status == "pending"
        ).count()

        return {
            "total_users": total_users,
            "agent_count": agent_count,
            "distributor_count": distributor_count,
            "member_count": member_count,
            "regular_user_count": regular_user_count,
            "today_new_users": today_new_users,
            "today_recharge_total": today_recharge_total,
            "pending_ticket_count": pending_ticket_count,
        }


def get_dashboard_service() -> DashboardService:
    return DashboardService()
