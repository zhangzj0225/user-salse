"""收益看板相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EarningsSummary(BaseModel):
    """收益汇总。"""
    pending_balance: str  # 记账余额（待提现）
    withdrawn_total: str  # 已提现总额
    available_balance: str  # 可用余额（= 记账余额 - 已冻结提现金额）


class EarningsRecord(BaseModel):
    """收益明细条目。"""
    id: int
    amount: str
    type: str  # first_reward / followup_reward / team_bonus / recommend / sale_commission
    source_user_id: Optional[int] = None
    source_email: Optional[str] = None
    business_id: str
    created_at: datetime


class EarningsListResponse(BaseModel):
    """收益明细列表响应。"""
    summary: EarningsSummary
    records: list[EarningsRecord]
    total: int
