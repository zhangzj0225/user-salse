"""License API 端点。"""

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.license import (
    LicenseActivateRequest,
    LicenseInfo,
    LicenseVerifyRequest,
    LicenseVerifyResponse,
)
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


@router.get("/users/me/licenses", response_model=dict)
def get_my_licenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: LicenseService = Depends(get_license_service),
):
    """查看我的 License 列表。"""
    licenses = service.get_user_licenses(current_user.id, db)
    return {"data": [LicenseInfo.model_validate(l).model_dump() for l in licenses]}


@router.post("/license/verify", response_model=LicenseVerifyResponse)
def verify_license(
    request: LicenseVerifyRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
    service: LicenseService = Depends(get_license_service),
):
    """验证 License（供舆情系统调用）。

    需要 X-API-Key 头部鉴权。
    """
    if not hmac.compare_digest(x_api_key, settings.LICENSE_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API Key")

    result = service.verify_license(code=request.code, db=db)
    # 如果验证通过且传入了 business_user_id，自动激活
    if result["valid"] and request.business_user_id:
        service.activate_license(
            code=request.code,
            business_user_id=request.business_user_id,
            business_user_info=request.business_user_info,
            db=db,
        )
        return LicenseVerifyResponse(
            valid=True,
            status="已激活",
            license_info=None,
        )
    return LicenseVerifyResponse(
        valid=result["valid"],
        status=result["message"],
        license_info=None,
    )


@router.post("/license/activate", response_model=dict)
def activate_license(
    request: LicenseActivateRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
    service: LicenseService = Depends(get_license_service),
):
    """激活 License（供舆情系统调用）。

    需要 X-API-Key 头部鉴权。
    """
    if not hmac.compare_digest(x_api_key, settings.LICENSE_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API Key")

    result = service.activate_license(
        code=request.code,
        business_user_id=request.business_user_id,
        business_user_info=request.business_user_info,
        db=db,
    )
    return {"data": result}
