"""用户管理相关 Pydantic schemas (Story 4.1)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminUserInfo(BaseModel):
    """管理员视图用户信息。"""
    id: int
    email: str
    nickname: Optional[str] = None
    role: str
    status: str
    parent_id: Optional[int] = None
    parent_email: Optional[str] = None
    account_quota: int = 0
    account_used: int = 0
    created_at: datetime


class UserDetail(BaseModel):
    """用户详情（含团队统计 + 收益汇总）。"""
    id: int
    email: str
    nickname: Optional[str] = None
    role: str
    status: str
    parent_id: Optional[int] = None
    parent_email: Optional[str] = None
    account_quota: int = 0
    account_used: int = 0
    created_at: datetime
    # 团队统计
    direct_downline_count: int = 0
    total_downline_count: int = 0
    # 收益汇总
    total_commission: str = "0.00"
    withdrawn_total: str = "0.00"
    available_balance: str = "0.00"


class UserListResponse(BaseModel):
    """用户列表响应。"""
    users: list[AdminUserInfo]
    total: int
