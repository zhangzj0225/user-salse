import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import AdminInfo, LoginRequest, SendEmailCodeRequest, UserInfo
from app.services.auth_service import AdminAuthService, get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


@router.post("/send-email-code", response_model=dict)
def send_email_code(request: SendEmailCodeRequest, db: Session = Depends(get_db)):
    auth_service = get_auth_service()
    try:
        code = auth_service.send_email_code(request.email, request.scene, db)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Email service not available")
    result = {"message": "验证码已发送"}
    if settings.AUTH_MODE == "mock":
        result["code"] = code
    return {"data": result}


@router.post("/login", response_model=dict)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    auth_service = get_auth_service()
    try:
        user, token = auth_service.authenticate(
            request.email, request.code, request.invite_code, db
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Auth service not available")

    return {
        "data": {
            "token": token,
            "user": UserInfo.model_validate(user).model_dump(),
        }
    }


@router.post("/admin-login", response_model=dict)
def admin_login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    service = AdminAuthService()
    try:
        admin, token = service.authenticate(request.username, request.password, db)
        logger.info(
            "Admin login successful: user_id=%d username=%s", admin.id, admin.username
        )
    except ValueError:
        logger.warning("Admin login failed: username=%s", request.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "data": {
            "token": token,
            "admin": AdminInfo.model_validate(admin).model_dump(),
        }
    }
