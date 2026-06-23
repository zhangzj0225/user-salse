"""额度销售服务（场景 A）。"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.email_verification_code import EmailVerificationCode
from app.models.payment import Payment
from app.models.user import User
from app.services.auth_service import _verify_email_code
from app.services.license_service import LicenseService
from app.services.quota_service import QuotaService

logger = logging.getLogger(__name__)

# 场景 A: 固定销售 888 会员
SALE_AMOUNT = Decimal("888.00")
SALE_TARGET_ROLE = "member_license"
SALE_VERIFY_SCENE = "sale_verify"


class SaleService:
    """额度销售服务（场景 A — 代客支付，不产生佣金）。

    邮箱验证流程：
    1. 前端调用 POST /auth/send-email-code (scene=sale_verify) 发送验证码
    2. 前端调用 POST /sales (customer_email + verification_code) 确认销售
    """

    def __init__(self):
        self._quota_service = QuotaService()
        self._license_service = LicenseService()

    def sell_account(
        self,
        seller_id: int,
        customer_email: str,
        verification_code: str,
        db: Session,
    ) -> dict:
        """额度销售：为客户开通 888 会员。

        流程：
        1. 校验销售者资格（agent/distributor + 额度 > 0）
        2. 校验客户邮箱未被注册
        3. 校验邮箱验证码
        4. 消耗 1 个额度（行锁防并发）
        5. 创建客户 User（role=distributor, parent_id=seller_id）
        6. 创建 Payment 记录（status=approved，供 sales_records 查询）
        7. 生成 License
        8. 审计日志
        9. 不调用 CommissionEngine（场景 A 不产生佣金）

        返回: {"customer_id", "payment_id", "remaining_quota"}
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

        # 3. 校验邮箱验证码
        _verify_email_code(db, customer_email, SALE_VERIFY_SCENE, verification_code)

        try:
            # 4. 消耗额度（含行锁）— 在邮箱检查之后，避免竞态条件
            self._quota_service.consume_quota(seller_id, 1, db)

            # 5. 创建客户
            customer = User(
                email=customer_email,
                role="distributor",
                status="active",
                parent_id=seller_id,
            )
            db.add(customer)
            db.flush()

            # 6. 创建 Payment 记录（approved 状态，供 sales_records 查询）
            # F2: reviewed_by 不写 seller_id —— 该列 FK 指向 admin_users.id，
            # 写 User.id 在生产 MySQL 会 IntegrityError。sale 流程无管理员审核，
            # reviewed_by 留 null。销售者关系由 parent_id + 审计日志 business_id=sale_{id} 体现。
            payment = Payment(
                user_id=customer.id,
                email=customer_email,
                amount=SALE_AMOUNT,
                target_role=SALE_TARGET_ROLE,
                channel="offline",
                status="paid",
                reviewed_by=None,
                reviewed_at=datetime.now(timezone.utc),
            )
            db.add(payment)
            db.flush()

            # 7. 生成 License
            self._license_service.generate_for_payment(
                user_id=customer.id,
                payment_id=payment.id,
                target_role=SALE_TARGET_ROLE,
                db=db,
            )

            # 8. 审计日志
            log = AuditLog(
                action="quota_sale",
                operator_type="user",
                operator_id=seller_id,
                target_type="user",
                target_id=customer.id,
                old_value=None,
                new_value={
                    "customer_email": customer_email,
                    "role": "distributor",
                    "parent_id": seller_id,
                    "payment_id": payment.id,
                    "amount": str(SALE_AMOUNT),
                },
                business_id=f"sale_{payment.id}",
            )
            db.add(log)

            db.commit()
            db.refresh(seller)
            db.refresh(customer)
            db.refresh(payment)
        except Exception:
            db.rollback()
            raise

        logger.info(
            "Quota sale completed: seller=%d customer=%d payment=%d remaining=%d",
            seller_id, customer.id, payment.id,
            seller.account_quota - seller.account_used,
        )

        return {
            "customer_id": customer.id,
            "payment_id": payment.id,
            "remaining_quota": seller.account_quota - seller.account_used,
        }


def get_sale_service() -> SaleService:
    return SaleService()
