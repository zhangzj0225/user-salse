"""License API 端点。"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.license import LicenseInfo, VerifyLicenseRequest, VerifyLicenseResponse
from app.services.license_service import LicenseService, get_license_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["license"])


@router.get("/users/me/license", response_model=LicenseInfo)
def get_my_license(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: LicenseService = Depends(get_license_service),
):
    """查看我的 License（"我的"页面）。"""
    license_obj = service.get_user_license(current_user.id, db)
    if not license_obj:
        raise HTTPException(status_code=404, detail="暂无 License")
    return license_obj


@router.post("/license/verify", response_model=VerifyLicenseResponse)
def verify_license(
    request: VerifyLicenseRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
    service: LicenseService = Depends(get_license_service),
):
    """验证并激活 License（供舆情系统调用）。

    需要 X-API-Key 头部鉴权。
    """
    if x_api_key != settings.LICENSE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    result = service.verify_and_activate(
        code=request.code,
        email=request.email,
        db=db,
    )
    return result
