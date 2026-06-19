"""额度销售 API 端点（场景 A）。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.sale import SellAccountRequest, SellAccountResponse
from app.services.sale_service import SaleService, get_sale_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", response_model=SellAccountResponse)
def sell_account_endpoint(
    request: SellAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: SaleService = Depends(get_sale_service),
):
    """额度销售（场景 A）。

    代理/经销商消耗 1 个可售额度，为客户开通 888 会员。
    不产生佣金。客户上级 = 销售者。
    """
    if current_user.role not in ("agent", "distributor"):
        raise HTTPException(
            status_code=403,
            detail="仅代理和经销商可销售账号",
        )

    try:
        result = service.sell_account(
            seller_id=current_user.id,
            customer_email=request.customer_email,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
