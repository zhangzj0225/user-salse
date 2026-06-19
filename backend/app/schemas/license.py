"""License 相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class LicenseInfo(BaseModel):
    """用户 License 信息（"我的"页面）。"""
    code: str
    email: str
    source: str
    status: str
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class VerifyLicenseRequest(BaseModel):
    """License 验证请求（舆情系统调用）。"""
    code: str
    email: EmailStr


class VerifyLicenseResponse(BaseModel):
    """License 验证响应。"""
    success: bool
    message: str
