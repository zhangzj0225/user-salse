"""收益看板服务。"""

import logging
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.commission_record import CommissionRecord
from app.models.ticket import Ticket
from app.models.user import User

logger = logging.getLogger(__name__)

# 收益类型映射到中文显示名
TYPE_DISPLAY_MAP = {
    "first_reward": "首次奖励",
    "followup_reward": "后续收益",
    "team_bonus": "长期奖励",
    "recommend": "推荐返佣",
    "sale_commission": "销售佣金",
}

VALID_FILTER_TYPES = set(TYPE_DISPLAY_MAP.keys())


def calculate_balance_summary(user_id: int, db: Session) -> tuple[Decimal, Decimal, Decimal]:
    """计算用户余额三元组，供 earnings / withdrawal 复用，避免两处公式漂移。

    返回: (total_commission, withdrawn_total, available_balance)
      - total_commission: 记账余额（所有佣金总和，毛额）
        ⚠️ D4: 内部变量名 total_commission，API 响应字段名为 pending_balance
        （见 EarningsSummary schema）。两者是同一个值，仅命名不同。
      - withdrawn_total:  已提现（paid 工单总和），仅用于展示，不参与可用余额计算
      - available_balance: 可用余额 = total_commission - pending 工单（已冻结提现金额）
        PRD 定义：可用余额 = 记账余额 - 已冻结提现金额。
        已提现（paid）的部分不应再扣减，因为记账余额是毛额，已提现金额仅作展示。

    可用余额等价于: total_commission - sum(status = 'pending' 工单)
    """
    total_result = db.query(
        func.coalesce(func.sum(CommissionRecord.amount), 0)
    ).filter(CommissionRecord.user_id == user_id).scalar()
    total_commission = Decimal(total_result)

    pending_result = db.query(
        func.coalesce(func.sum(Ticket.amount), 0)
    ).filter(Ticket.user_id == user_id, Ticket.status == "pending").scalar()
    pending = Decimal(pending_result)

    paid_result = db.query(
        func.coalesce(func.sum(Ticket.amount), 0)
    ).filter(Ticket.user_id == user_id, Ticket.status == "paid").scalar()
    withdrawn_total = Decimal(paid_result)

    # 可用 = 总佣金 - pending 冻结 - paid 已提现
    available_balance = total_commission - pending - withdrawn_total
    return total_commission, withdrawn_total, available_balance


class EarningsService:
    """收益看板查询服务。"""

    def get_earnings(
        self,
        user_id: int,
        db: Session,
        record_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """获取用户收益汇总 + 明细列表。

        Args:
            user_id: 用户 ID
            db: 数据库会话
            record_type: 筛选类型（可选）
            limit: 每页条数
            offset: 偏移量

        返回: {
            "summary": {pending_balance, withdrawn_total, available_balance},
            "records": [...],
            "total": int,
        }
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        # 筛选条件
        query = db.query(CommissionRecord).filter(
            CommissionRecord.user_id == user_id
        )
        if record_type:
            if record_type not in VALID_FILTER_TYPES:
                raise ValueError(f"无效的收益类型: {record_type}")
            query = query.filter(CommissionRecord.type == record_type)

        # 总数
        total = query.count()

        # 明细列表（时间倒序）
        records = (
            query.order_by(CommissionRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # 汇总：记账余额 / 已提现 / 可用余额（复用公共函数，避免与 withdrawal 公式漂移）
        pending_balance, withdrawn, available = calculate_balance_summary(user_id, db)

        # 构建 source_email
        source_ids = {r.source_user_id for r in records if r.source_user_id}
        source_users = {}
        if source_ids:
            source_user_list = (
                db.query(User)
                .filter(User.id.in_(source_ids))
                .all()
            )
            source_users = {u.id: u.email for u in source_user_list}

        return {
            "summary": {
                "pending_balance": str(pending_balance),
                "withdrawn_total": str(withdrawn),
                "available_balance": str(available),
            },
            "records": [
                {
                    "id": r.id,
                    "amount": str(r.amount),
                    "type": r.type,
                    "source_user_id": r.source_user_id,
                    "source_email": source_users.get(r.source_user_id) if r.source_user_id else None,
                    "business_id": r.business_id,
                    "created_at": r.created_at,
                }
                for r in records
            ],
            "total": total,
        }


def get_earnings_service() -> EarningsService:
    return EarningsService()
