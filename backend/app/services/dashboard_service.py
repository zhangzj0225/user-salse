"""运营数据看板服务 (Story 4.3)。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.license import License
from app.models.payment import Payment
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

        # 今日数据 — 使用 func.date() 跨数据库兼容
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_new_users = db.query(User).filter(
            func.date(User.created_at) == today_str
        ).count()

        today_payment_result = db.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            func.date(Payment.created_at) == today_str,
            Payment.status == "paid",
        ).scalar()
        today_payment_total = str(Decimal(today_payment_result))

        # License 统计
        license_generated_count = db.query(License).count()
        license_activated_count = db.query(License).filter(
            License.status == "activated"
        ).count()

        # 工单统计
        pending_ticket_count = db.query(Ticket).filter(
            Ticket.status == "pending"
        ).count()

        return {
            "total_users": total_users,
            "agent_count": agent_count,
            "distributor_count": distributor_count,
            "today_new_users": today_new_users,
            "today_payment_total": today_payment_total,
            "license_generated_count": license_generated_count,
            "license_activated_count": license_activated_count,
            "pending_ticket_count": pending_ticket_count,
        }


def get_dashboard_service() -> DashboardService:
    return DashboardService()
