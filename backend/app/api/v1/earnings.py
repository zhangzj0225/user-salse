"""收益看板 API 端点。"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.earnings import EarningsListResponse
from app.services.earnings_service import EarningsService, get_earnings_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me", tags=["earnings"])


@router.get("/earnings", response_model=EarningsListResponse)
def get_earnings_endpoint(
    type: Optional[str] = Query(None, description="筛选类型: first_reward/followup_reward/team_bonus/recommend/sale_commission"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: EarningsService = Depends(get_earnings_service),
):
    """查看我的收益（汇总 + 明细列表）。

    返回记账余额、已提现总额、可用余额，以及按时间倒序的收益明细。
    支持按类型筛选。
    """
    try:
        result = service.get_earnings(
            user_id=current_user.id,
            db=db,
            record_type=type,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
