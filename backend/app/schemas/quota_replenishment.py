"""补购申请相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class QuotaReplenishRequest(BaseModel):
    """用户提交补购申请请求。

    amount=0 表示申请补充到当前角色默认额度（代理22/经销商11）。
    """

    email: EmailStr = Field(..., description="申请人邮箱（需与登录用户一致）")
    amount: int = Field(
        default=0,
        ge=0,
        description="申请追加额度，0 表示使用角色默认额度",
    )


class QuotaReplenishResponse(BaseModel):
    """补购申请响应。"""

    id: int
    user_id: int
    old_quota: int
    requested_amount: int
    status: str
    reject_reason: Optional[str] = None
    reviewed_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuotaReplenishReviewRequest(BaseModel):
    """管理员审核补购申请请求。"""

    action: str = Field(..., pattern=r"^(approved|rejected)$", description="审核动作")
    reject_reason: Optional[str] = Field(
        default=None, min_length=1, max_length=256, description="拒绝原因（仅 reject 时必填）"
    )

    @model_validator(mode="after")
    def check_reject_reason(self):
        if self.action == "rejected" and not self.reject_reason:
            raise ValueError("拒绝时必须提供 reject_reason")
        return self


class QuotaReplenishListResponse(BaseModel):
    """补购申请列表响应。"""

    items: list[QuotaReplenishResponse]
    total: int
