"""充值相关 Pydantic schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class CreateRechargeRequest(BaseModel):
    amount: int = Field(..., description="充值金额：888/5000/10000")


class RechargeInfo(BaseModel):
    id: int
    user_id: int
    amount: Decimal
    target_role: str
    status: str
    reject_reason: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        """DECIMAL 序列化为字符串 "888.00"。"""
        return f"{amount:.2f}"


class RejectRechargeRequest(BaseModel):
    reject_reason: str = Field(..., min_length=1, max_length=256)
