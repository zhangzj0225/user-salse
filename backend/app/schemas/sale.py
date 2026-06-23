"""额度销售相关 Pydantic schemas。"""

from pydantic import BaseModel, EmailStr, Field


class SellAccountRequest(BaseModel):
    """额度销售请求。"""
    customer_email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class SellAccountResponse(BaseModel):
    """额度销售响应。"""
    customer_id: int
    payment_id: int
    remaining_quota: int
