"""收益看板服务。"""

import logging
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.commission_record import CommissionRecord
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

        # 汇总：记账余额 = 所有佣金总和（提现功能未实现，withdrawn=0）
        all_records = (
            db.query(CommissionRecord)
            .filter(CommissionRecord.user_id == user_id)
            .all()
        )
        pending = sum((Decimal(r.amount) for r in all_records), Decimal("0.00"))
        withdrawn = Decimal("0.00")  # 提现功能在后续 Story 实现
        available = pending - withdrawn  # 无冻结金额

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
                "pending_balance": str(pending),
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
