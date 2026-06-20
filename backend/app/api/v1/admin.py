"""管理员 API 端点。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin_user import AdminUser
from app.models.user import User
from app.schemas.recharge import AdminRechargeInfo, RechargeInfo, RejectRechargeRequest
from app.schemas.ticket import (
    AdminTicketListResponse,
    RejectTicketRequest,
    TicketActionResponse,
)
from app.services.recharge_service import RechargeService, get_recharge_service
from app.services.withdrawal_service import WithdrawalService, get_withdrawal_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_VALID_STATUSES = ("pending", "approved", "rejected")


@router.get("/recharges", response_model=dict)
def list_recharges_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/approved/rejected"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: RechargeService = Depends(get_recharge_service),
):
    """管理员查看充值记录列表，支持状态筛选。"""
    # S2: 状态参数枚举校验
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_STATUSES}",
        )

    recharges = service.list_recharges(db, status=status)

    # S6: 管理员列表返回用户邮箱
    result = []
    for r in recharges:
        user = db.query(User).filter(User.id == r.user_id).first()
        info = AdminRechargeInfo.model_validate(r)
        info.user_email = user.email if user else ""
        result.append(info.model_dump())

    return {"data": result, "total": len(result)}


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


# ---- 工单管理（Story 3.13）----

_VALID_TICKET_STATUSES = ("pending", "paid", "rejected")


@router.get("/tickets", response_model=AdminTicketListResponse)
def list_tickets_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/paid/rejected"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """管理员查看提现工单列表，支持状态筛选。"""
    if status is not None and status not in _VALID_TICKET_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_TICKET_STATUSES}",
        )

    tickets = service.list_all_tickets(db, status=status)
    return {"tickets": tickets, "total": len(tickets)}


@router.post("/tickets/{ticket_id}/approve", response_model=TicketActionResponse)
def approve_ticket_endpoint(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """管理员确认打款。"""
    try:
        result = service.approve_ticket(ticket_id, current_admin.id, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/tickets/{ticket_id}/reject", response_model=TicketActionResponse)
def reject_ticket_endpoint(
    ticket_id: int,
    request: RejectTicketRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """管理员拒绝工单，金额解冻退回。"""
    try:
        result = service.reject_ticket(
            ticket_id, current_admin.id, request.reject_reason, db
        )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return result


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
