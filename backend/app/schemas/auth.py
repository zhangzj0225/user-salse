from typing import Optional

from pydantic import BaseModel, Field


class SendSmsRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")


class LoginRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    sms_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    invite_code: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    status: str

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    token: str
    user: UserInfo


class AdminInfo(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}
