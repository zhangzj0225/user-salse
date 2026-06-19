"""提现工单 API 端点。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.ticket import (
    CreateTicketRequest,
    CreateTicketResponse,
    TicketInfo,
    TicketListResponse,
)
from app.services.withdrawal_service import WithdrawalService, get_withdrawal_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me", tags=["withdrawal"])


@router.post("/tickets", response_model=CreateTicketResponse)
def create_ticket_endpoint(
    request: CreateTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """提交提现申请。

    生成工单（状态 pending），冻结对应金额。
    """
    try:
        result = service.create_ticket(
            user_id=current_user.id,
            amount=request.amount,
            payment_method=request.payment_method,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/paid/rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """查看我的提现工单列表。"""
    try:
        tickets = service.list_user_tickets(current_user.id, db, status)
        return {"tickets": tickets, "total": len(tickets)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
