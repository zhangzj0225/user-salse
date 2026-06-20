"""消息通知服务 (Story 5.2)。

通知事件：
- 下级注册 (subordinate_registered)
- 佣金入账 (commission_credited)
- 工单状态变更 (ticket_status_changed)
- 充值审核通过 (recharge_approved)

所有通知写入 notification_logs 表。
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.notification_log import NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    """消息通知服务 — 写入 notification_logs。"""

    @staticmethod
    def send(
        user_id: int,
        event_type: str,
        content: dict[str, Any] | None,
        db: Session,
    ) -> NotificationLog:
        """写入一条通知记录。

        注意：此方法仅 flush（不 commit），由调用方事务统一 commit。
        """
        notification = NotificationLog(
            user_id=user_id,
            event_type=event_type,
            content=content,
            sent=False,
        )
        db.add(notification)
        db.flush()

        logger.info(
            "Notification created: user_id=%d event_type=%s",
            user_id, event_type,
        )
        return notification

    @staticmethod
    def notify_subordinate_registered(
        parent_id: int, child_email: str, db: Session
    ) -> NotificationLog:
        """通知上级：有新下级注册。"""
        return NotificationService.send(
            user_id=parent_id,
            event_type="subordinate_registered",
            content={"child_email": child_email},
            db=db,
        )

    @staticmethod
    def notify_commission_credited(
        user_id: int, amount: str, commission_type: str, db: Session
    ) -> NotificationLog:
        """通知用户：佣金入账。"""
        return NotificationService.send(
            user_id=user_id,
            event_type="commission_credited",
            content={"amount": amount, "type": commission_type},
            db=db,
        )

    @staticmethod
    def notify_ticket_status_changed(
        user_id: int, ticket_id: int, old_status: str, new_status: str,
        reason: str | None, db: Session,
    ) -> NotificationLog:
        """通知用户：工单状态变更。"""
        return NotificationService.send(
            user_id=user_id,
            event_type="ticket_status_changed",
            content={
                "ticket_id": ticket_id,
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
            },
            db=db,
        )

    @staticmethod
    def notify_recharge_approved(
        user_id: int, amount: str, new_role: str, db: Session
    ) -> NotificationLog:
        """通知用户：充值审核通过。"""
        return NotificationService.send(
            user_id=user_id,
            event_type="recharge_approved",
            content={"amount": amount, "new_role": new_role},
            db=db,
        )

    @staticmethod
    def list_user_notifications(
        user_id: int, db: Session, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]:
        """列出用户的通知。"""
        query = db.query(NotificationLog).filter(NotificationLog.user_id == user_id)
        total = query.count()
        logs = (
            query.order_by(NotificationLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "event_type": l.event_type,
                "content": l.content,
                "sent": l.sent,
                "created_at": l.created_at,
            }
            for l in logs
        ], total

    @staticmethod
    def mark_as_read(notification_id: int, user_id: int, db: Session) -> bool:
        """标记通知为已读（sent=True）。"""
        notification = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.id == notification_id,
                NotificationLog.user_id == user_id,
            )
            .first()
        )
        if not notification:
            return False
        notification.sent = True
        db.commit()
        return True


def get_notification_service() -> NotificationService:
    return NotificationService()
