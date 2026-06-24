"""支付 API 端点（用户端）。"""

import hashlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentResponse,
)
from app.services.payment_service import PaymentService, get_payment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCallbackRequest(BaseModel):
    """支付回调请求（webhook）。"""

    payment_id: int
    payment_no: str = Field(..., min_length=1, max_length=128)


@router.post("/create", response_model=dict, status_code=201)
def create_payment_endpoint(
    request: PaymentCreateRequest,
    db: Session = Depends(get_db),
    service: PaymentService = Depends(get_payment_service),
):
    """创建支付订单。"""
    try:
        payment = service.create_payment(
            email=request.email,
            amount=request.amount,
            referral_code=request.referral_code,
            redirect_url=request.redirect_url,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": PaymentResponse.model_validate(payment).model_dump()}


@router.get("", response_model=dict)
def list_payments_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """查看我的支付记录。"""
    payments = service.list_user_payments(current_user.id, db)
    return {
        "data": [
            PaymentResponse.model_validate(p).model_dump() for p in payments
        ],
        "total": len(payments),
    }


@router.get("/{payment_id}/status", response_model=dict)
def get_payment_status_endpoint(
    payment_id: int,
    db: Session = Depends(get_db),
    service: PaymentService = Depends(get_payment_service),
):
    """查询支付状态（公开接口，支付页面无需登录）。"""
    try:
        result = service.get_payment_status(payment_id, db)
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": result}


def _verify_callback_signature(payment_id: int, payment_no: str, signature: str) -> bool:
    """验证支付回调签名（HMAC-SHA256 内部 webhook 签名）。

    TODO: 对接真实微信/支付宝支付网关时，需替换为官方签名验证：
    - 微信支付 V3: RSA-SHA256 签名验证（使用微信平台公钥）
    - 支付宝: RSA2 签名验证（使用支付宝公钥）
    当前为内部 webhook 签名机制，适用于模拟支付或内部支付网关。
    """
    import hmac
    payload = f"{payment_id}:{payment_no}"
    expected = hmac.new(
        settings.PAYMENT_CALLBACK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/callback", response_model=dict)
def payment_callback_endpoint(
    request: PaymentCallbackRequest,
    db: Session = Depends(get_db),
    x_signature: str = Header(..., alias="X-Signature"),
    service: PaymentService = Depends(get_payment_service),
):
    """支付回调（webhook，需签名验证）。"""
    if not _verify_callback_signature(request.payment_id, request.payment_no, x_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payment = service.process_payment_callback(
            payment_id=request.payment_id,
            payment_no=request.payment_no,
            db=db,
        )
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": PaymentResponse.model_validate(payment).model_dump()}
