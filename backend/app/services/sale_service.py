"""额度销售服务（场景 A）。"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.recharge import Recharge
from app.models.user import User
from app.services.license_service import LicenseService
from app.services.quota_service import QuotaService

logger = logging.getLogger(__name__)

# 场景 A: 固定销售 888 会员
SALE_AMOUNT = 888
SALE_TARGET_ROLE = "member"


class SaleService:
    """额度销售服务（场景 A — 代客充值，不产生佣金）。"""

    def __init__(self):
        self._quota_service = QuotaService()
        self._license_service = LicenseService()

    def sell_account(
        self,
        seller_id: int,
        customer_email: str,
        db: Session,
    ) -> dict:
        """额度销售：为客戶开通 888 会员。

        流程：
        1. 校验销售者资格（agent/distributor + 额度 > 0）
        2. 校验客户邮箱未被注册
        3. 消耗 1 个额度（行锁防并发）
        4. 创建客户 User（role=member, parent_id=seller_id）
        5. 创建 Recharge 记录（status=approved，供 sales_records 查询）
        6. 生成 License
        7. 审计日志
        8. 不调用 CommissionEngine（场景 A 不产生佣金）

        返回: {"customer_id", "recharge_id", "remaining_quota"}
        """
        # 1. 校验销售者
        seller = db.query(User).filter(User.id == seller_id).first()
        if not seller:
            raise ValueError("销售者不存在")
        if seller.role not in ("agent", "distributor"):
            raise ValueError("无权销售账号")
        if seller.account_quota - seller.account_used <= 0:
            raise ValueError("额度不足，无法销售")

        # 2. 校验客户邮箱
        customer_email = customer_email.strip().lower()
        existing = db.query(User).filter(User.email == customer_email).first()
        if existing:
            raise ValueError("客户邮箱已注册")

        # 3. 消耗额度（含行锁）
        self._quota_service.consume_quota(seller_id, 1, db)

        # 4. 创建客户
        customer = User(
            email=customer_email,
            role=SALE_TARGET_ROLE,
            status="active",
            parent_id=seller_id,
        )
        db.add(customer)
        db.flush()

        # 5. 创建 Recharge 记录（approved 状态，供 sales_records 查询）
        recharge = Recharge(
            user_id=customer.id,
            amount=SALE_AMOUNT,
            target_role=SALE_TARGET_ROLE,
            status="approved",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(recharge)
        db.flush()

        # 6. 生成 License
        self._license_service.generate_for_recharge(
            user_id=customer.id,
            email=customer.email,
            recharge_id=recharge.id,
            target_role=SALE_TARGET_ROLE,
            db=db,
        )

        # 7. 审计日志
        log = AuditLog(
            action="quota_sale",
            operator_type="user",
            operator_id=seller_id,
            target_type="user",
            target_id=customer.id,
            old_value=None,
            new_value={
                "customer_email": customer_email,
                "role": SALE_TARGET_ROLE,
                "parent_id": seller_id,
                "recharge_id": recharge.id,
                "amount": SALE_AMOUNT,
            },
            business_id=f"sale_{recharge.id}",
        )
        db.add(log)

        db.commit()
        db.refresh(seller)
        db.refresh(customer)
        db.refresh(recharge)

        logger.info(
            "Quota sale completed: seller=%d customer=%d recharge=%d remaining=%d",
            seller_id, customer.id, recharge.id,
            seller.account_quota - seller.account_used,
        )

        return {
            "customer_id": customer.id,
            "recharge_id": recharge.id,
            "remaining_quota": seller.account_quota - seller.account_used,
        }


def get_sale_service() -> SaleService:
    return SaleService()
