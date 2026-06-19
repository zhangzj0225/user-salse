"""邀请码 API 端点。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.invite_code import (
    InviteCodeInfo,
    VerifyInviteCodeRequest,
    VerifyInviteCodeResponse,
)
from app.services.invite_service import InviteCodeService, get_invite_code_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invite-codes", tags=["invite-codes"])


@router.post("", response_model=dict)
def generate_invite_code_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: InviteCodeService = Depends(get_invite_code_service),
):
    """生成新的邀请码。用户可生成多个未使用的邀请码。"""
    try:
        ic = service.generate_for_user(current_user.id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(
        "Invite code generated via API: user_id=%d code=%s",
        current_user.id, ic.code,
    )
    return {"data": InviteCodeInfo.model_validate(ic).model_dump()}


@router.get("", response_model=dict)
def list_invite_codes_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: InviteCodeService = Depends(get_invite_code_service),
):
    """列出当前用户生成的所有邀请码。"""
    codes = service.list_user_codes(current_user.id, db)
    return {
        "data": [
            InviteCodeInfo.model_validate(ic).model_dump() for ic in codes
        ]
    }


@router.post("/verify", response_model=dict)
def verify_invite_code_endpoint(
    request: VerifyInviteCodeRequest,
    db: Session = Depends(get_db),
    service: InviteCodeService = Depends(get_invite_code_service),
):
    """验证邀请码：签名校验 + 数据库查找。

    S4: 公开接口，无需认证（注册前需验证邀请码）。
    """
    result = service.verify_code(request.code, db)
    response = VerifyInviteCodeResponse(**result)
    return {"data": response.model_dump()}
