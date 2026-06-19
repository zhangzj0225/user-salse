"""额度 API 端点。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.quota import QuotaInfo
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
