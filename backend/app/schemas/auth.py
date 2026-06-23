from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SendEmailCodeRequest(BaseModel):
    email: EmailStr
    scene: str = Field(default="login", pattern=r"^(login|sale_verify)$")


class LoginRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class UserInfo(BaseModel):
    id: int
    email: str
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
