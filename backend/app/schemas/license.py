"""License 相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LicenseInfo(BaseModel):
    """用户 License 信息（"我的"页面）。"""

    code: str
    source: str
    status: str
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LicenseVerifyRequest(BaseModel):
    """License 验证请求（舆情系统调用）。"""

    code: str
    business_user_id: Optional[str] = Field(default=None, max_length=128)
    business_user_info: Optional[str] = Field(default=None, max_length=512)


class LicenseActivateRequest(BaseModel):
    """License 激活请求。"""

    code: str
    business_user_id: str = Field(..., min_length=1, max_length=128)
    business_user_info: Optional[str] = Field(default=None, max_length=512)


class LicenseVerifyResponse(BaseModel):
    """License 验证响应。"""

    valid: bool
    status: str
    license_info: Optional[LicenseInfo] = None
