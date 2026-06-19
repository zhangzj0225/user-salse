"""管理员 API 端点。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin_user import AdminUser
from app.schemas.recharge import RechargeInfo, RejectRechargeRequest
from app.services.recharge_service import RechargeService, get_recharge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/recharges", response_model=dict)
def list_recharges_endpoint(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: RechargeService = Depends(get_recharge_service),
):
    """管理员查看充值记录列表，支持状态筛选。"""
    recharges = service.list_recharges(db, status=status)
    return {
        "data": [
            RechargeInfo.model_validate(r).model_dump() for r in recharges
        ],
        "total": len(recharges),
    }


@router.post("/recharges/{recharge_id}/approve", response_model=dict)
def approve_recharge_endpoint(
    recharge_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: RechargeService = Depends(get_recharge_service),
):
    """批准充值申请。"""
    try:
        recharge = service.approve_recharge(recharge_id, current_admin.id, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": RechargeInfo.model_validate(recharge).model_dump()}


@router.post("/recharges/{recharge_id}/reject", response_model=dict)
def reject_recharge_endpoint(
    recharge_id: int,
    request: RejectRechargeRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: RechargeService = Depends(get_recharge_service),
):
    """拒绝充值申请。"""
    try:
        recharge = service.reject_recharge(
            recharge_id, current_admin.id, request.reject_reason, db
        )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": RechargeInfo.model_validate(recharge).model_dump()}
