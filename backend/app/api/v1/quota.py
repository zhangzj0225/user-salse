"""额度 API 端点。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.license import GenerateLicenseResponse
from app.schemas.quota import QuotaInfo
from app.schemas.quota_replenishment import (
    QuotaReplenishRequest,
    QuotaReplenishListResponse,
    QuotaReplenishResponse,
)
from app.services.license_service import LicenseService, get_license_service
from app.services.quota_replenishment_service import (
    QuotaReplenishmentService,
    get_quota_replenishment_service,
)
from app.services.quota_service import QuotaService, get_quota_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("", response_model=QuotaInfo)
def get_quota_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: QuotaService = Depends(get_quota_service),
):
    """查看我的可售额度。

    仅代理（agent）和经销商（distributor）可访问。
    普通用户和 888 会员返回 403。
    """
    if current_user.role not in ("agent", "distributor"):
        raise HTTPException(
            status_code=403,
            detail="仅代理和经销商可查看可售额度",
        )

    info = service.get_quota_info(current_user.id, db)
    return info


@router.post("/replenish", response_model=dict)
def submit_replenish_request(
    request: QuotaReplenishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: QuotaReplenishmentService = Depends(get_quota_replenishment_service),
):
    """提交补购申请。

    代理/经销商额度耗尽后申请补充额度。
    amount=0 表示申请补充到当前角色默认额度（代理22/经销商11）。
    """
    # 校验邮箱与当前登录用户一致
    if request.email.strip().lower() != current_user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="只能为自己提交补购申请",
        )

    try:
        result = service.create_replenish_request(
            user_email=current_user.email,
            amount=request.amount,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"data": result}


@router.get("/replenish/status", response_model=dict)
def get_replenish_status(
    status: Optional[str] = Query(None, description="筛选状态: pending/approved/rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: QuotaReplenishmentService = Depends(get_quota_replenishment_service),
):
    """查看我的补购申请状态。"""
    try:
        requests = service.list_user_requests(
            user_id=current_user.id,
            db=db,
            status=status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"data": requests, "total": len(requests)}


@router.post("/generate-license", response_model=GenerateLicenseResponse)
def generate_license_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    quota_service: QuotaService = Depends(get_quota_service),
    license_service: LicenseService = Depends(get_license_service),
):
    """生成裸 License（不绑定用户）。

    仅代理（agent）和经销商（distributor）可访问。
    消耗 1 个可售额度，生成不绑定用户的 License Code，
    由代理/经销商交付给客户自行激活。

    与 POST /sales 的区别：
    - /sales：创建客户 User + 绑定 License（场景 A 代客支付）
    - /generate-license：仅生成裸 License Code，不创建用户（场景 A 独立 Code 交付）
    """
    # 1. 角色校验
    if current_user.role not in ("agent", "distributor"):
        raise HTTPException(
            status_code=403,
            detail="仅代理和经销商可生成 License",
        )

    # 2. 校验可售额度 > 0（快速失败，不用锁；实际防并发由 consume_quota 行锁保证）
    if not quota_service.check_quota_available(current_user.id, 1, db):
        raise HTTPException(status_code=400, detail="额度不足，无法生成 License")

    try:
        # 3. 消耗 1 个额度（with_for_update 行锁防并发超额）
        try:
            quota_service.consume_quota(current_user.id, 1, db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 4. 生成不绑定用户的裸 License
        license_obj = license_service.generate_for_payment(
            user_id=None,
            payment_id=0,
            target_role="member_license",
            db=db,
            source="sale",
            generated_by=current_user.id,
        )

        # 5. 记录审计日志
        log = AuditLog(
            action="license_generate_quota",
            operator_type="user",
            operator_id=current_user.id,
            target_type="license",
            target_id=license_obj.id,
            new_value={
                "source": "sale",
                "code": license_obj.code,
                "generated_by": current_user.id,
            },
            business_id=f"license_{license_obj.id}",
        )
        db.add(log)

        db.commit()
        db.refresh(current_user)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("generate_license failed: user_id=%d", current_user.id)
        raise HTTPException(status_code=500, detail="生成 License 失败")

    # 6. 返回 License code 和剩余额度
    remaining = current_user.account_quota - current_user.account_used
    return GenerateLicenseResponse(
        code=license_obj.code,
        remaining_quota=remaining,
        message="License 生成成功",
    )
