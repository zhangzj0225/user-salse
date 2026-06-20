"""提现工单服务。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.commission_record import CommissionRecord
from app.models.ticket import Ticket
from app.models.user import User

logger = logging.getLogger(__name__)

MIN_WITHDRAWAL_AMOUNT = Decimal("100.00")


class WithdrawalService:
    """提现工单服务。"""

    def _get_available_balance(self, user_id: int, db: Session) -> Decimal:
        """计算可用余额 = 记账余额 - 已冻结金额（pending 工单总额）。"""
        # 记账余额 = 所有佣金总和（SQL 聚合）
        pending_result = db.query(
            func.coalesce(func.sum(CommissionRecord.amount), 0)
        ).filter(CommissionRecord.user_id == user_id).scalar()
        pending_balance = Decimal(pending_result)

        # 已冻结 = pending 工单总额（SQL 聚合）
        frozen_result = db.query(
            func.coalesce(func.sum(Ticket.amount), 0)
        ).filter(
            Ticket.user_id == user_id, Ticket.status == "pending"
        ).scalar()
        frozen_amount = Decimal(frozen_result)

        return pending_balance - frozen_amount

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
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

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

        # 3. 校验可用余额 — 行锁防并发超额
        # 锁定该用户的 pending 工单行，防止并发提现同时通过余额检查
        db.query(Ticket).filter(
            Ticket.user_id == user_id, Ticket.status == "pending"
        ).with_for_update().all()

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


def get_withdrawal_service() -> WithdrawalService:
    return WithdrawalService()
