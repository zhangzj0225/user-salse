"""管理员 API 端点。"""

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin_user import AdminUser
from app.models.commission_config import CommissionConfig
from app.models.config_change_log import ConfigChangeLog
from app.models.license import License
from app.models.system_config import SystemConfig
from app.models.user import User
from app.schemas.payment import PaymentApproveRequest, PaymentResponse
from app.schemas.ticket import (
    AdminTicketListResponse,
    RejectTicketRequest,
    TicketActionResponse,
)
from app.schemas.admin_user import UserDetail, UserListResponse
from app.schemas.dashboard import DashboardStats
from app.schemas.commission_config import (
    CommissionConfigListResponse,
    CommissionConfigUpdateRequest,
)
from app.schemas.system_config import (
    ConfigChangeLogListResponse,
    ConfigListResponse,
    ConfigUpdateRequest,
)
from app.services.dashboard_service import DashboardService, get_dashboard_service
from app.services.license_service import (
    CURRENT_KEY_VERSION,
    _generate_license_code,
)
from app.services.payment_service import PaymentService, get_payment_service
from app.services.referral_service import ReferralService, get_referral_service
from app.services.system_config_service import SystemConfigService, get_system_config_service
from app.services.user_management_service import UserManagementService, get_user_management_service
from app.services.withdrawal_service import WithdrawalService, get_withdrawal_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_VALID_STATUSES = ("pending", "paid", "failed")


@router.get("/payments", response_model=dict)
def list_payments_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/paid/failed"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: PaymentService = Depends(get_payment_service),
):
    """管理员查看支付记录列表，支持状态筛选和分页。"""
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_STATUSES}",
        )

    payments, total = service.list_payments(db, status=status, limit=limit, offset=offset)

    result = [
        PaymentResponse.model_validate(p).model_dump() for p in payments
    ]

    return {"data": result, "total": total, "limit": limit, "offset": offset}


@router.post("/payments/{payment_id}/approve", response_model=dict)
def approve_payment_endpoint(
    payment_id: int,
    request: PaymentApproveRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: PaymentService = Depends(get_payment_service),
):
    """批准支付申请（可补填推荐码）。"""
    try:
        payment = service.approve_payment(
            payment_id, current_admin.id, db,
            referral_code=request.referral_code,
        )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": PaymentResponse.model_validate(payment).model_dump()}


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


# ---- 佣金配置管理（FR-13）----

_VALID_COMMISSION_ROLES = ("distributor", "agent")
_VALID_REWARD_TYPES = ("fixed", "percentage")


class CommissionConfigUpdateRequest(BaseModel):
    """修改佣金配置请求。"""

    reward_value: Decimal = Field(..., gt=0, description="奖励金额/比例")
    reward_type: Optional[str] = Field(None, pattern=r"^(fixed|percentage)$", description="奖励类型，不传则保持不变")


@router.get("/commission-configs", response_model=dict)
def list_commission_configs_endpoint(
    role: Optional[str] = Query(None, description="筛选角色: distributor/agent"),
    scene: Optional[str] = Query(None, description="筛选场景"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """管理员查看佣金配置列表，支持角色和场景筛选，按 role + scene 排序。"""
    if role is not None and role not in _VALID_COMMISSION_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的角色参数，允许值: {_VALID_COMMISSION_ROLES}",
        )

    query = db.query(CommissionConfig)
    if role:
        query = query.filter(CommissionConfig.role == role)
    if scene:
        query = query.filter(CommissionConfig.scene == scene)

    total = query.count()
    configs = (
        query.order_by(CommissionConfig.role, CommissionConfig.scene)
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = [
        {
            "id": c.id,
            "role": c.role,
            "scene": c.scene,
            "reward_type": c.reward_type,
            "reward_value": float(c.reward_value),
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in configs
    ]

    return {"data": result, "total": total, "limit": limit, "offset": offset}


@router.get("/commission-configs/{config_id}", response_model=dict)
def get_commission_config_endpoint(
    config_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """管理员查看单条佣金配置详情。"""
    config = db.query(CommissionConfig).filter(CommissionConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="佣金配置不存在")
    return {
        "data": {
            "id": config.id,
            "role": config.role,
            "scene": config.scene,
            "reward_type": config.reward_type,
            "reward_value": float(config.reward_value),
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }
    }


@router.put("/commission-configs/{config_id}", response_model=dict)
def update_commission_config_endpoint(
    config_id: int,
    request: CommissionConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """管理员修改佣金配置。role 和 scene 不可修改（唯一标识），变更自动记入 ConfigChangeLog。"""
    config = (
        db.query(CommissionConfig)
        .filter(CommissionConfig.id == config_id)
        .with_for_update()
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="佣金配置不存在")

    # 记录旧值
    old_reward_type = config.reward_type
    old_reward_value = float(config.reward_value)
    old_value_str = f"reward_type={old_reward_type}, reward_value={old_reward_value}"

    # 更新字段（reward_type 可选：不传则保持原值）
    if request.reward_type is not None:
        config.reward_type = request.reward_type
    config.reward_value = request.reward_value

    new_value_str = f"reward_type={config.reward_type}, reward_value={float(config.reward_value)}"

    # 写入变更日志
    log_entry = ConfigChangeLog(
        admin_id=current_admin.id,
        config_key=f"commission_config:{config_id}",
        old_value=old_value_str,
        new_value=new_value_str,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(config)

    logger.info(
        "Commission config updated: id=%d role=%s scene=%s old=(%s) new=(%s) admin_id=%d",
        config_id, config.role, config.scene, old_value_str, new_value_str, current_admin.id,
    )

    return {
        "data": {
            "id": config.id,
            "role": config.role,
            "scene": config.scene,
            "reward_type": config.reward_type,
            "reward_value": float(config.reward_value),
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }
    }


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

_VALID_ROLES = ("distributor", "agent")


@router.get("/users", response_model=UserListResponse)
def list_users_endpoint(
    search: Optional[str] = Query(None, description="搜索邮箱/昵称"),
    role: Optional[str] = Query(None, description="角色筛选: distributor/agent"),
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


class CreateSeedUserRequest(BaseModel):
    """创建种子用户请求。"""

    email: EmailStr
    role: str = Field(..., pattern=r"^(distributor|agent)$")
    referral_code: Optional[str] = Field(default=None, max_length=128)


@router.post("/users/create", response_model=dict)
def create_seed_user_endpoint(
    request: CreateSeedUserRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    referral_service: ReferralService = Depends(get_referral_service),
):
    """创建种子用户（跳过支付流程，自动分配额度 + License + 推荐码）。

    S5: 额度从 SystemConfig 动态读取，fallback 到硬编码默认值 (agent=22, distributor=11)。
    """
    email = request.email.strip().lower()

    # 检查邮箱是否已存在
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    # 验证推荐码（如有），获取推荐人
    parent_id = None
    if request.referral_code:
        result = referral_service.validate_referral_code(request.referral_code, db)
        if not result["valid"]:
            raise HTTPException(status_code=400, detail="推荐码无效")
        parent_id = result["user_id"]

    # S5: 从 SystemConfig 动态读取额度，fallback 到硬编码默认值
    _QUOTA_FALLBACK = {"distributor": 11, "agent": 22}
    quota = _QUOTA_FALLBACK.get(request.role, 0)
    try:
        config_key = f"quota_for_{request.role}"
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == config_key
        ).first()
        if config and config.config_value is not None:
            try:
                quota = int(config.config_value)
                logger.info(
                    "Seed user quota from SystemConfig: role=%s quota=%d",
                    request.role, quota,
                )
            except (ValueError, TypeError):
                logger.warning(
                    "SystemConfig '%s' value '%s' 无法转为整数，"
                    "fallback 到硬编码: %d",
                    config_key, config.config_value, quota,
                )
        else:
            logger.warning(
                "SystemConfig key '%s' 不存在，fallback 到硬编码: %d",
                config_key, quota,
            )
    except Exception as e:
        logger.warning(
            "无法读取 SystemConfig 额度配置 (%s)，fallback 到硬编码: %d",
            e, quota,
        )
    user = User(
        email=email,
        role=request.role,
        status="active",
        parent_id=parent_id,
        account_quota=quota,
    )
    db.add(user)
    db.flush()

    # 生成推荐码
    rc = referral_service.get_or_create_referral_code(user.id, db)
    user.referral_code = rc.code
    user.referral_code_generated = 1

    # 生成 License（source=role_builtin）
    license_code = _generate_license_code(user.id)
    license_obj = License(
        code=license_code,
        user_id=user.id,
        source="role_builtin",
        source_id=None,
        status="unused",
        key_version=CURRENT_KEY_VERSION,
    )
    db.add(license_obj)

    db.commit()
    db.refresh(user)

    from app.services.notification_service import NotificationService
    NotificationService.notify_seed_user_created(
        user_id=user.id, email=user.email, role=user.role, db=db,
    )
    db.commit()

    logger.info(
        "Seed user created: user_id=%d email=%s role=%s",
        user.id, user.email, user.role,
    )
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "account_quota": user.account_quota,
            "referral_code": rc.code,
            "license_code": license_code,
        }
    }


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


class RejectPaymentRequest(BaseModel):
    """拒绝支付请求。"""

    reject_reason: str = Field(..., min_length=1, max_length=256)


@router.post("/payments/{payment_id}/reject", response_model=dict)
def reject_payment_endpoint(
    payment_id: int,
    request: RejectPaymentRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    service: PaymentService = Depends(get_payment_service),
):
    """拒绝支付申请。"""
    try:
        payment = service.reject_payment(
            payment_id, current_admin.id, request.reject_reason, db
        )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": PaymentResponse.model_validate(payment).model_dump()}


# ---- 补购申请审核（FR-7）----

_VALID_REPLENISH_STATUSES = ("pending", "approved", "rejected")


@router.get("/quota-replenishments", response_model=dict)
def list_quota_replenishments_endpoint(
    status: Optional[str] = Query(None, description="筛选状态: pending/approved/rejected"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """管理员查看补购申请列表，支持状态筛选和分页。"""
    from app.services.quota_replenishment_service import (
        QuotaReplenishmentService,
        get_quota_replenishment_service,
    )

    if status is not None and status not in _VALID_REPLENISH_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态参数，允许值: {_VALID_REPLENISH_STATUSES}",
        )

    service = get_quota_replenishment_service()
    try:
        requests, total = service.list_all_requests(
            db, status=status, limit=limit, offset=offset
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"data": requests, "total": total, "limit": limit, "offset": offset}


@router.post("/quota-replenishments/{request_id}/review", response_model=dict)
def review_quota_replenishment_endpoint(
    request_id: int,
    request: "QuotaReplenishReviewRequest",
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """管理员审核补购申请（通过/拒绝）。

    - approved: 追加额度到用户账户
    - rejected: 拒绝申请，需提供 reject_reason
    """
    from app.schemas.quota_replenishment import QuotaReplenishReviewRequest
    from app.services.quota_replenishment_service import (
        QuotaReplenishmentService,
        get_quota_replenishment_service,
    )

    service = get_quota_replenishment_service()
    try:
        if request.action == "approved":
            result = service.approve_replenish(request_id, current_admin.id, db)
        else:
            result = service.reject_replenish(
                request_id, current_admin.id, request.reject_reason, db
            )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return {"data": result}
