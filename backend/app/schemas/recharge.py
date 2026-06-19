"""充值相关 Pydantic schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator


VALID_AMOUNTS = (888, 5000, 10000)


class CreateRechargeRequest(BaseModel):
    amount: int = Field(..., description="充值金额：888/5000/10000")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v not in VALID_AMOUNTS:
            raise ValueError(f"充值金额必须为 {VALID_AMOUNTS} 之一")
        return v


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


class AdminRechargeInfo(RechargeInfo):
    """管理员端充值信息，含用户邮箱。"""

    user_email: str = ""

    model_config = {"from_attributes": True}


class RejectRechargeRequest(BaseModel):
    reject_reason: str = Field(..., min_length=1, max_length=256)
