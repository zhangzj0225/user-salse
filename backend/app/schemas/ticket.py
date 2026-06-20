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


class AdminTicketInfo(BaseModel):
    """管理员视图工单信息（含用户邮箱）。"""
    id: int
    user_id: int
    user_email: str
    amount: str
    payment_method: str
    status: str
    reject_reason: Optional[str] = None
    processed_by: Optional[int] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


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


class AdminTicketListResponse(BaseModel):
    """管理员工单列表响应。"""
    tickets: list[AdminTicketInfo]
    total: int


class RejectTicketRequest(BaseModel):
    """拒绝工单请求。"""
    reject_reason: str = Field(..., min_length=1, max_length=256)


class TicketActionResponse(BaseModel):
    """工单操作响应。"""
    id: int
    status: str
    processed_by: int
    processed_at: datetime
    reject_reason: Optional[str] = None
