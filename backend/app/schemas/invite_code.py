"""邀请码相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InviteCodeInfo(BaseModel):
    id: int
    code: str
    generator_id: int
    key_version: int
    used_by: Optional[int] = None
    used_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifyInviteCodeRequest(BaseModel):
    code: str


class VerifyInviteCodeResponse(BaseModel):
    valid: bool
    generator_id: Optional[int] = None
    used: bool
