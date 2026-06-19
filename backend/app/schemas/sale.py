"""额度销售相关 Pydantic schemas。"""

from pydantic import BaseModel, EmailStr, Field


class SellAccountRequest(BaseModel):
    """额度销售请求。"""
    customer_email: EmailStr


class SellAccountResponse(BaseModel):
    """额度销售响应。"""
    customer_id: int
    recharge_id: int
    remaining_quota: int
