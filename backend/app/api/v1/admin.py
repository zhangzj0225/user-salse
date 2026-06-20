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
from app.schemas.admin_user import UserDetail, UserListResponse
from app.schemas.dashboard import DashboardStats
from app.schemas.system_config import (
    ConfigChangeLogListResponse,
    ConfigListResponse,
    ConfigUpdateRequest,
)
from app.services.dashboard_service import DashboardService, get_dashboard_service
from app.services.recharge_service import RechargeService, get_recharge_service
from app.services.system_config_service import SystemConfigService, get_system_config_service
from app.services.user_management_service import UserManagementService, get_user_management_service
from app.services.withdrawal_service import WithdrawalService, get_withdrawal_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_VALID_STATUSES = ("pending", "approved", "rejected")


@router.get("/recharges", response_model=dict)
def list_recharges_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/approved/rejected"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: RechargeService = Depends(get_recharge_service),
):
    """管理员查看充值记录列表，支持状态筛选和分页。"""
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_STATUSES}",
        )

    recharges, total = service.list_recharges(db, status=status, limit=limit, offset=offset)

    # 批量加载用户邮箱
    user_ids = {r.user_id for r in recharges}
    users = {}
    if user_ids:
        user_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u.email for u in user_list}

    result = []
    for r in recharges:
        info = AdminRechargeInfo.model_validate(r)
        info.user_email = users.get(r.user_id, "")
        result.append(info.model_dump())

    return {"data": result, "total": total, "limit": limit, "offset": offset}


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


# ---- 系统参数配置（Story 4.4）----

@router.get("/configs", response_model=ConfigListResponse)
def list_configs_endpoint(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: SystemConfigService = Depends(get_system_config_service),
):
    """管理员查看系统参数配置列表。"""
    configs = service.list_configs(db)
    return {"configs": configs}


@router.get("/configs/{config_key}", response_model=dict)
def get_config_endpoint(
    config_key: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: SystemConfigService = Depends(get_system_config_service),
):
    """管理员查看单个配置项。"""
    try:
        result = service.get_config(config_key, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": result}


@router.put("/configs/{config_key}", response_model=dict)
def update_config_endpoint(
    config_key: str,
    request: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: SystemConfigService = Depends(get_system_config_service),
):
    """管理员更新系统参数配置，修改仅对新业务生效。"""
    try:
        result = service.update_config(config_key, request.config_value, current_admin.id, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": result}


@router.get("/config-change-logs", response_model=ConfigChangeLogListResponse)
def list_config_change_logs_endpoint(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: SystemConfigService = Depends(get_system_config_service),
):
    """管理员查看配置变更日志。"""
    logs = service.list_change_logs(db, limit=limit)
    return {"logs": logs}


# ---- 运营数据看板（Story 4.3）----

@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: DashboardService = Depends(get_dashboard_service),
):
    """管理员运营数据看板：用户统计 + 今日数据 + 待处理工单。"""
    return service.get_stats(db)


# ---- 用户管理（Story 4.1）----

_VALID_ROLES = ("user", "member", "distributor", "agent")


@router.get("/users", response_model=UserListResponse)
def list_users_endpoint(
    search: Optional[str] = Query(None, description="搜索邮箱/昵称"),
    role: Optional[str] = Query(None, description="角色筛选: user/member/distributor/agent"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: UserManagementService = Depends(get_user_management_service),
):
    """管理员查看用户列表，支持搜索和角色筛选。"""
    if role is not None and role not in _VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的角色参数，允许值: {_VALID_ROLES}",
        )

    users, total = service.list_users(db, search=search, role=role, limit=limit, offset=offset)
    return {"users": users, "total": total}


@router.get("/users/{user_id}", response_model=UserDetail)
def get_user_detail_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: UserManagementService = Depends(get_user_management_service),
):
    """管理员查看用户详情：基本信息 + 团队统计 + 收益汇总。"""
    try:
        result = service.get_user_detail(user_id, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---- 工单管理（Story 3.13）----

_VALID_TICKET_STATUSES = ("pending", "paid", "rejected")


@router.get("/tickets", response_model=AdminTicketListResponse)
def list_tickets_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/paid/rejected"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: WithdrawalService = Depends(get_withdrawal_service),
):
    """管理员查看提现工单列表，支持状态筛选和分页。"""
    if status is not None and status not in _VALID_TICKET_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_TICKET_STATUSES}",
        )

    tickets, total = service.list_all_tickets(db, status=status, limit=limit, offset=offset)
    return {"tickets": tickets, "total": total}


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
