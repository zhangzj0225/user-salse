"""推荐码 API 端点。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.referral_code import ReferralCodeResponse
from app.services.referral_service import ReferralService, get_referral_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/referral-code", tags=["referral-code"])


@router.get("", response_model=dict)
def get_my_referral_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ReferralService = Depends(get_referral_service),
):
    """获取我的持久推荐码（get_or_create）。

    每用户1个持久码，已存在则返回，不存在则创建。
    """
    try:
        rc = service.get_or_create_referral_code(current_user.id, db)
        db.commit()
        db.refresh(rc)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(
        "Referral code retrieved via API: user_id=%d code=%s",
        current_user.id, rc.code,
    )
    return {"data": ReferralCodeResponse.model_validate(rc).model_dump()}
