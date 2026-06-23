"""支付相关 Pydantic schemas。"""

import os
import urllib.parse
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


VALID_AMOUNTS = (888, 5000, 10000)
VALID_TARGET_ROLES = ("member_license", "distributor", "agent")

# redirect_url 白名单（逗号分隔的 hostname 列表，可通过环境变量覆盖）
_REDIRECT_ALLOWED_HOSTS: set = set(
    h.strip().lower()
    for h in os.environ.get("REDIRECT_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
)


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

    @field_validator("redirect_url")
    @classmethod
    def validate_redirect_url(cls, v: Optional[str]) -> Optional[str]:
        """校验 redirect_url hostname 在白名单内（防开放重定向）。"""
        if v is None:
            return v
        try:
            parsed = urllib.parse.urlparse(v)
        except Exception:
            raise ValueError("redirect_url 格式无效")
        if parsed.scheme not in ("http", "https"):
            raise ValueError("redirect_url 必须使用 http 或 https 协议")
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError("redirect_url 必须包含有效的主机名")
        if hostname not in _REDIRECT_ALLOWED_HOSTS:
            raise ValueError(
                f"redirect_url 主机名 '{hostname}' 不在白名单中。"
                f"允许的主机: {sorted(_REDIRECT_ALLOWED_HOSTS)}"
            )
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
