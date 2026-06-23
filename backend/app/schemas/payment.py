"""支付相关 Pydantic schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


VALID_AMOUNTS = (888, 5000, 10000)
VALID_TARGET_ROLES = ("member_license", "distributor", "agent")


class PaymentCreateRequest(BaseModel):
    """创建支付订单请求。"""

    email: EmailStr
    amount: int = Field(..., description="支付金额：888/5000/10000")
    referral_code: Optional[str] = Field(default=None, max_length=128)
    redirect_url: Optional[str] = Field(default=None, max_length=512)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v not in VALID_AMOUNTS:
            raise ValueError(f"支付金额必须为 {VALID_AMOUNTS} 之一")
        return v


class PaymentResponse(BaseModel):
    """支付订单响应。"""

    id: int
    email: str
    amount: Decimal
    target_role: str
    status: str
    channel: Optional[str] = None
    referral_code: Optional[str] = None
    license_code: Optional[str] = None
    reject_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        """DECIMAL 序列化为字符串 "888.00"。"""
        return f"{amount:.2f}"


class PaymentStatusResponse(BaseModel):
    """支付状态查询响应。"""

    id: int
    status: str
    license_code: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentApproveRequest(BaseModel):
    """管理员线下审核请求（可选填推荐码）。"""

    referral_code: Optional[str] = Field(default=None, max_length=128)
