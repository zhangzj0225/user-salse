"""充值 API 端点（用户端）。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.recharge import CreateRechargeRequest, RechargeInfo
from app.services.recharge_service import RechargeService, get_recharge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recharges", tags=["recharges"])


@router.post("", response_model=dict, status_code=201)
def create_recharge_endpoint(
    request: CreateRechargeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: RechargeService = Depends(get_recharge_service),
):
    """提交充值申请。"""
    try:
        recharge = service.create_recharge(current_user.id, request.amount, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": RechargeInfo.model_validate(recharge).model_dump()}


@router.get("", response_model=dict)
def list_recharges_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: RechargeService = Depends(get_recharge_service),
):
    """查看我的充值记录。"""
    recharges = service.list_user_recharges(current_user.id, db)
    return {
        "data": [
            RechargeInfo.model_validate(r).model_dump() for r in recharges
        ],
        "total": len(recharges),
    }
