"""提现工单相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    """提现申请请求。"""
    amount: str = Field(..., description="提现金额（字符串，避免浮点精度问题）")
    payment_method: str = Field(..., min_length=1, max_length=256, description="收款信息")


class TicketInfo(BaseModel):
    """工单信息。"""
    id: int
    user_id: int
    amount: str
    payment_method: str
    status: str
    reject_reason: Optional[str] = None
    processed_by: Optional[int] = None
    processed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTicketResponse(BaseModel):
    """提现申请响应。"""
    ticket_id: int
    amount: str
    status: str
    available_balance: str


class TicketListResponse(BaseModel):
    """工单列表响应。"""
    tickets: list[TicketInfo]
    total: int
