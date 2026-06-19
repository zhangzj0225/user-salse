"""额度相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SalesRecord(BaseModel):
    recharge_id: int
    child_email: str
    amount: str
    target_role: str
    approved_at: Optional[str] = None


class QuotaInfo(BaseModel):
    role: str
    account_quota: int
    account_used: int
    remaining: int
    sales_records: list[SalesRecord]
