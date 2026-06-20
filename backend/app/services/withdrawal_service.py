"""提现工单服务。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.user import User
from app.services.earnings_service import calculate_balance_summary

logger = logging.getLogger(__name__)

MIN_WITHDRAWAL_AMOUNT = Decimal("100.00")


class WithdrawalService:
    """提现工单服务。"""

    def _get_available_balance(self, user_id: int, db: Session) -> Decimal:
        """计算可用余额 = 总佣金 - pending 工单 - paid 工单。

        paid 工单即已提现金额，必须扣减，否则 approve 后可用余额回升导致双重支付。
        复用 earnings_service.calculate_balance_summary，避免两处公式漂移。
        """
        _, _, available = calculate_balance_summary(user_id, db)
        return available

    def create_ticket(
        self,
        user_id: int,
        amount: str,
        payment_method: str,
        db: Session,
    ) -> dict:
        """创建提现工单。

        1. 校验金额格式
        2. 校验金额 >= 最低提现额（100 元）
        3. 校验金额 <= 可用余额（行锁防并发）
        4. 创建工单（status=pending）
        5. 冻结金额（通过 pending 工单自然冻结）
        6. 审计日志

        返回: {"ticket_id", "amount", "status", "available_balance"}
        """
        # 1. 校验金额格式
        try:
            amount_decimal = Decimal(amount)
        except (InvalidOperation, ValueError):
            raise ValueError("金额格式无效")

        if amount_decimal <= 0:
            raise ValueError("提现金额必须大于 0")

        # 2. 校验最低提现额
        if amount_decimal < MIN_WITHDRAWAL_AMOUNT:
            raise ValueError(f"提现金额不能低于最低提现额 {MIN_WITHDRAWAL_AMOUNT} 元")

        # 3. 校验可用余额 — 锁 User 行防并发超额提现
        # F6: 原先锁 pending 工单集合，用户无 pending 工单时锁空集，靠 gap lock 兜底
        # （无复合索引、隔离级别降级即失效）。改为锁 User 行，串行化同一用户的并发提现。
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if not user:
            raise ValueError("用户不存在")

        available = self._get_available_balance(user_id, db)
        if amount_decimal > available:
            raise ValueError("提现金额超过可用余额")

        # 4. 创建工单
        ticket = Ticket(
            user_id=user_id,
            amount=amount_decimal,
            payment_method=payment_method,
            status="pending",
        )
        db.add(ticket)
        db.flush()

        # 5. 审计日志
        audit = AuditLog(
            action="withdrawal_create",
            target_type="ticket",
            target_id=ticket.id,
            operator_type="user",
            operator_id=user_id,
            old_value=None,
            new_value={"amount": str(amount_decimal), "payment_method": payment_method},
        )
        db.add(audit)
        db.commit()
        db.refresh(ticket)

        # 6. 计算冻结后可用余额
        new_available = self._get_available_balance(user_id, db)

        logger.info(
            "Withdrawal ticket created: user_id=%d ticket_id=%d amount=%s",
            user_id, ticket.id, amount,
        )

        return {
            "ticket_id": ticket.id,
            "amount": str(ticket.amount),
            "status": ticket.status,
            "available_balance": str(new_available),
        }

    def list_user_tickets(
        self,
        user_id: int,
        db: Session,
        status: str | None = None,
    ) -> list[dict]:
        """查看用户的工单列表。"""
        query = db.query(Ticket).filter(Ticket.user_id == user_id)
        if status:
            if status not in ("pending", "paid", "rejected"):
                raise ValueError("无效的工单状态")
            query = query.filter(Ticket.status == status)

        tickets = query.order_by(Ticket.created_at.desc()).all()
        return [
            {
                "id": t.id,
                "user_id": t.user_id,
                "amount": str(t.amount),
                "payment_method": t.payment_method,
                "status": t.status,
                "reject_reason": t.reject_reason,
                "processed_by": t.processed_by,
                "processed_at": t.processed_at,
                "created_at": t.created_at,
            }
            for t in tickets
        ]

    def list_all_tickets(
        self,
        db: Session,
        status: str | None = None,
    ) -> list[dict]:
        """管理员查看所有工单列表（含用户邮箱）。"""
        query = db.query(Ticket)
        if status:
            if status not in ("pending", "paid", "rejected"):
                raise ValueError("无效的工单状态")
            query = query.filter(Ticket.status == status)

        tickets = query.order_by(Ticket.created_at.desc()).all()

        # 批量加载用户邮箱
        user_ids = {t.user_id for t in tickets}
        users = {}
        if user_ids:
            user_list = db.query(User).filter(User.id.in_(user_ids)).all()
            users = {u.id: u.email for u in user_list}

        return [
            {
                "id": t.id,
                "user_id": t.user_id,
                "user_email": users.get(t.user_id, ""),
                "amount": str(t.amount),
                "payment_method": t.payment_method,
                "status": t.status,
                "reject_reason": t.reject_reason,
                "processed_by": t.processed_by,
                "processed_at": t.processed_at,
                "created_at": t.created_at,
            }
            for t in tickets
        ]

    def approve_ticket(
        self,
        ticket_id: int,
        admin_id: int,
        db: Session,
    ) -> dict:
        """管理员确认打款 — status → paid。

        打款后该工单进入 paid 状态，可用余额公式（calculate_balance_summary）
        会扣减 paid 工单总额，故已提现金额不会回流到可用余额，防止双重支付。
        """
        # 行锁防并发
        ticket = (
            db.query(Ticket)
            .filter(Ticket.id == ticket_id)
            .with_for_update()
            .first()
        )
        if not ticket:
            raise ValueError("工单不存在")

        if ticket.status != "pending":
            raise ValueError("工单已处理")

        old_status = ticket.status
        ticket.status = "paid"
        ticket.processed_by = admin_id
        ticket.processed_at = datetime.now(timezone.utc)

        # 审计日志
        audit = AuditLog(
            action="ticket_approve",
            target_type="ticket",
            target_id=ticket.id,
            operator_type="admin",
            operator_id=admin_id,
            old_value={"status": old_status},
            new_value={"status": "paid"},
        )
        db.add(audit)
        db.commit()
        db.refresh(ticket)

        logger.info(
            "Ticket approved: ticket_id=%d admin_id=%d", ticket_id, admin_id,
        )

        return {
            "id": ticket.id,
            "status": ticket.status,
            "processed_by": ticket.processed_by,
            "processed_at": ticket.processed_at,
            "reject_reason": ticket.reject_reason,
        }

    def reject_ticket(
        self,
        ticket_id: int,
        admin_id: int,
        reject_reason: str,
        db: Session,
    ) -> dict:
        """管理员拒绝工单 — status → rejected，金额解冻退回（pending 变 rejected 后不再冻结）。"""
        # 行锁防并发
        ticket = (
            db.query(Ticket)
            .filter(Ticket.id == ticket_id)
            .with_for_update()
            .first()
        )
        if not ticket:
            raise ValueError("工单不存在")

        if ticket.status != "pending":
            raise ValueError("工单已处理")

        old_status = ticket.status
        ticket.status = "rejected"
        ticket.reject_reason = reject_reason
        ticket.processed_by = admin_id
        ticket.processed_at = datetime.now(timezone.utc)

        # 审计日志
        audit = AuditLog(
            action="ticket_reject",
            target_type="ticket",
            target_id=ticket.id,
            operator_type="admin",
            operator_id=admin_id,
            old_value={"status": old_status},
            new_value={"status": "rejected", "reject_reason": reject_reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(ticket)

        logger.info(
            "Ticket rejected: ticket_id=%d admin_id=%d reason=%s",
            ticket_id, admin_id, reject_reason,
        )

        return {
            "id": ticket.id,
            "status": ticket.status,
            "processed_by": ticket.processed_by,
            "processed_at": ticket.processed_at,
            "reject_reason": ticket.reject_reason,
        }


def get_withdrawal_service() -> WithdrawalService:
    return WithdrawalService()
