"""额度相关 Pydantic schemas。"""

from typing import Optional

from pydantic import BaseModel


class SalesRecord(BaseModel):
    payment_id: int
    child_email: str
    amount: str
    target_role: Optional[str] = None
    approved_at: Optional[str] = None


class QuotaInfo(BaseModel):
    role: str
    account_quota: int
    account_used: int
    remaining: int
    can_replenish: bool
    sales_records: list[SalesRecord]
