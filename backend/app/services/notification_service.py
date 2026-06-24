"""消息通知服务 (Story 5.2)。

通知事件：
- 下级支付 (subordinate_paid)
- 佣金入账 (commission_credited)
- 工单状态变更 (ticket_status_changed)
- 支付审核通过 (payment_approved)

所有通知写入 notification_logs 表。
"""

import logging
from decimal import Decimal
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
    def notify_subordinate_paid(
        parent_id: int, child_email: str, amount: int, db: Session
    ) -> NotificationLog:
        """通知上级：下级支付成功。"""
        return NotificationService.send(
            user_id=parent_id,
            event_type="subordinate_paid",
            content={"child_email": child_email, "amount": str(amount)},
            db=db,
        )

    @staticmethod
    def notify_commission_credited(
        user_id: int, amount: str, commission_type: str, db: Session
    ) -> NotificationLog:
        """通知用户：佣金入账。"""
        # S6: 格式化金额，避免 Decimal 原始字符串如 "488.4000"
        try:
            formatted_amount = str(Decimal(amount).quantize(Decimal("0.01")))
        except Exception:
            formatted_amount = amount
        return NotificationService.send(
            user_id=user_id,
            event_type="commission_credited",
            content={"amount": formatted_amount, "type": commission_type},
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
    def notify_payment_approved(
        user_id: int, amount: str, new_role: str, db: Session
    ) -> NotificationLog:
        """通知用户：支付审核通过。"""
        return NotificationService.send(
            user_id=user_id,
            event_type="payment_approved",
            content={"amount": amount, "new_role": new_role},
            db=db,
        )

    @staticmethod
    def _send_notification_email(to_email: str, event_type: str, content: dict | None) -> None:
        """通过 SMTP 发送通知邮件（best-effort，失败仅记日志）。"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.core.config import settings

        subject = f"足球舆情系统 - 通知: {event_type}"
        body = f"""
您有一条新通知：

事件类型：{event_type}
内容：{content}

— 足球舆情系统
""".strip()

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT
            ) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT
            ) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())

        logger.info("Notification email sent: to=%s event_type=%s", to_email, event_type)

    @staticmethod
    def notify_seed_user_created(user_id, email, role, db):
        return NotificationService.send(
            user_id=user_id,
            event_type="seed_user_created",
            content={"email": email, "role": role, "login_guide": "请使用邮箱验证码登录分销系统"},
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
        """标记通知为已读（sent=True）。flush-only，由调用方 commit。"""
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
        db.flush()
        return True


def get_notification_service() -> NotificationService:
    return NotificationService()
