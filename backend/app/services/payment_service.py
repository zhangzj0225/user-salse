"""支付服务."""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ROLE_LEVEL
from app.services.system_config_service import get_dynamic_payment_configs
from app.models.payment import Payment
from app.models.referral_relationship import ReferralRelationship
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.commission_service import CommissionEngine
from app.services.license_service import LicenseService
from app.services.referral_service import ReferralService

logger = logging.getLogger(__name__)


class PaymentService:
    """支付订单、回调、审核服务。"""

    def __init__(self):
        self._license_service = LicenseService()
        self._referral_service = ReferralService()

    def _get_payment(
        self, payment_id: int, db: Session, *, for_update: bool = False
    ) -> Payment | None:
        """查询支付记录，可选行锁。"""
        query = db.query(Payment).filter(Payment.id == payment_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    # ── 创建支付订单 ──────────────────────────────────────

    def create_payment(
        self,
        email: str,
        amount: int,
        referral_code: str | None,
        redirect_url: str | None,
        db: Session,
    ) -> Payment:
        """创建支付订单。

        支付金额由 SystemConfig 动态配置（fallback 到 constants.py 默认值）。
        - member_license: user_id=NULL
        - distributor: 检查email是否已存在用户
        - agent: 检查email是否已存在用户
        """
        # S5: 从 SystemConfig 动态读取有效金额，fallback 到 constants.py
        configs = get_dynamic_payment_configs(db)
        valid_amounts = configs["valid_amounts"]
        amount_role_map = configs["amount_role_map"]

        if amount not in valid_amounts:
            raise ValueError(
                f"支付金额必须为 {sorted(valid_amounts)} 之一"
            )

        email = email.strip().lower()
        target_role = amount_role_map[amount]

        # 查找已有用户（用于自我推荐检查；5000/10000 也用于后续逻辑）
        existing_user = db.query(User).filter(User.email == email).first()

        # 检查是否有 pending 支付（防止重复提交）
        existing_pending = (
            db.query(Payment)
            .filter(Payment.email == email, Payment.status == "pending")
            .first()
        )
        if existing_pending:
            raise ValueError("已有待处理的支付订单")

        # 验证推荐码（如有）
        if referral_code:
            result = self._referral_service.validate_referral_code(referral_code, db)
            if not result["valid"]:
                raise ValueError("推荐码无效")
            # 自我推荐检查
            referrer_id = result["user_id"]
            if existing_user and existing_user.id == referrer_id:
                raise ValueError("不能使用自己的推荐码")

        payment = Payment(
            user_id=None,
            email=email,
            amount=amount,
            target_role=target_role,
            referral_code=referral_code,
            channel="online",
            status="pending",
            redirect_url=redirect_url,
            pending_user_key=int(hashlib.md5(email.encode()).hexdigest()[:8], 16),
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        logger.info(
            "Payment created: email=%s amount=%d target_role=%s payment_id=%d",
            email, amount, target_role, payment.id,
        )
        return payment

    # ── 支付成功处理（回调与审核共用） ────────────────────

    def _process_payment_success(self, payment: Payment, db: Session) -> None:
        """处理支付成功的业务逻辑（回调和管理员审核共用）。

        只 flush 不 commit，由调用方统一 commit。
        S5: 根据 payment.target_role 分支（而非硬编码金额），target_role
        在 create_payment 时已由动态配置决定。
        """
        if payment.target_role == "member_license":
            self._handle_license_payment(payment, db)
        elif payment.target_role in ("distributor", "agent"):
            self._handle_role_payment(payment, db, payment.target_role)
        else:
            raise ValueError(f"非法支付 target_role: {payment.target_role}")

    def _handle_license_payment(self, payment: Payment, db: Session) -> None:
        """888 支付：生成 License + 邮件发送 + 佣金计算。"""
        license_obj = self._license_service.generate_for_payment(
            user_id=None,
            payment_id=payment.id,
            target_role=payment.target_role,
            db=db,
        )
        if license_obj:
            payment.license_code = license_obj.code
            self._send_license_email(payment.email, license_obj.code)

        # 佣金计算（如有推荐码）
        engine = CommissionEngine(db)
        records = engine.process_payment(payment_id=payment.id)

        # 推荐关系记录 + 通知推荐人
        if payment.referral_code:
            from app.services.referral_service import ReferralService
            result = ReferralService().validate_referral_code(payment.referral_code, db)
            if result["valid"]:
                referrer_id = result["user_id"]
                # 创建推荐关系记录（888 支付无下级用户）
                rel = ReferralRelationship(
                    parent_user_id=referrer_id,
                    child_user_id=None,
                    referral_code=payment.referral_code,
                    payment_id=payment.id,
                )
                db.add(rel)
                # 通知推荐人（仅当有佣金记录时）
                if records:
                    from app.services.notification_service import NotificationService
                    NotificationService.notify_subordinate_paid(
                        parent_id=referrer_id,
                        child_email=payment.email,
                        amount=int(payment.amount),
                        db=db,
                    )

    def _handle_role_payment(
        self, payment: Payment, db: Session, role: str
    ) -> None:
        """5000/10000 支付：创建/更新账号 + 额度 + License + 推荐码 + 佣金。

        S5: 额度从 SystemConfig 动态读取，fallback 到 constants.py 硬编码默认值。
        """
        # 从 SystemConfig 动态读取额度配置
        configs = get_dynamic_payment_configs(db)
        role_quota_map = configs["role_quota_map"]
        quota = role_quota_map.get(role, 0)

        # 验证推荐码，获取推荐人
        referrer_id = None
        if payment.referral_code:
            result = self._referral_service.validate_referral_code(
                payment.referral_code, db
            )
            if result["valid"]:
                referrer_id = result["user_id"]

        # 查找已有用户（支持再次支付升级角色）
        user = db.query(User).filter(User.email == payment.email).first()
        if user:
            # 已有用户：更新角色和额度（各支付独立，额度累加）
            # 防止角色降级：仅当新角色等级 >= 当前角色等级时才更新
            new_level = ROLE_LEVEL.get(role, 0)
            current_level = ROLE_LEVEL.get(user.role, 0)
            if new_level >= current_level:
                user.role = role
            user.account_quota += quota
            # 设置上级关系（如果尚未设置且有推荐人）
            if not user.parent_id and referrer_id:
                user.parent_id = referrer_id
        else:
            # 新用户：创建账号
            user = User(
                email=payment.email,
                role=role,
                status="active",
                parent_id=referrer_id,
                account_quota=quota,
            )
            db.add(user)
            db.flush()
        payment.user_id = user.id

        # 生成推荐码
        rc = self._referral_service.get_or_create_referral_code(user.id, db)
        user.referral_code = rc.code
        user.referral_code_generated = 1

        # 生成 License
        license_obj = self._license_service.generate_for_payment(
            user_id=user.id,
            payment_id=payment.id,
            target_role=payment.target_role,
            db=db,
        )
        if license_obj:
            payment.license_code = license_obj.code

        # 佣金计算
        engine = CommissionEngine(db)
        engine.process_payment(payment_id=payment.id)

        # 通知上级有新下级支付
        if referrer_id:
            from app.services.notification_service import NotificationService
            NotificationService.notify_subordinate_paid(
                parent_id=referrer_id,
                child_email=payment.email,
                amount=int(payment.amount),
                db=db,
            )

        # 记录推荐关系（不可变追溯）
        if referrer_id:
            rel = ReferralRelationship(
                parent_user_id=referrer_id,
                child_user_id=user.id,
                referral_code=payment.referral_code,
                payment_id=payment.id,
            )
            db.add(rel)

    def _send_license_email(self, to_email: str, license_code: str) -> None:
        """通过 SMTP 发送 License 码邮件。"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            subject = "足球舆情系统 - License 激活码"
            body = f"""
您的 License 激活码是：{license_code}

请妥善保管，并在系统中激活使用。

— 足球舆情系统
""".strip()

            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(
                    settings.SMTP_HOST, settings.SMTP_PORT
                ) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASS)
                    server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(
                    settings.SMTP_HOST, settings.SMTP_PORT
                ) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASS)
                    server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())

            logger.info("License email sent: to=%s", to_email)
        except Exception as e:
            logger.error(
                "Failed to send license email: to=%s error=%s", to_email, e
            )

    # ── 支付回调 ──────────────────────────────────────────

    def process_payment_callback(
        self, payment_id: int, payment_no: str, db: Session
    ) -> Payment:
        """支付回调处理（在线支付成功后第三方回调）。"""
        # M2: 行锁防止并发处理
        payment = self._get_payment(payment_id, db, for_update=True)
        if not payment:
            raise ValueError("支付订单不存在")

        # 幂等保护：已处理则直接返回
        if payment.status == "paid":
            logger.info("Payment already processed: payment_id=%d", payment_id)
            return payment

        if payment.status != "pending":
            raise ValueError("支付订单状态异常")

        # 处理支付成功逻辑
        self._process_payment_success(payment, db)

        # 更新支付记录
        payment.status = "paid"
        payment.payment_no = payment_no
        payment.pending_user_key = None

        AuditService.log(
            action="payment_callback",
            operator_type="system",
            target_type="payment",
            target_id=payment.id,
            old_value={"status": "pending"},
            new_value={"status": "paid", "payment_no": payment_no},
            business_id=f"payment_{payment.id}",
            db=db,
        )

        # 通知用户支付成功（仅有关联用户时）
        if payment.user_id:
            from app.services.notification_service import NotificationService
            NotificationService.notify_payment_approved(
                user_id=payment.user_id,
                amount=str(int(payment.amount)),
                new_role=payment.target_role,
                db=db,
            )

        db.commit()
        db.refresh(payment)
        logger.info(
            "Payment callback processed: payment_id=%d status=paid", payment.id
        )
        return payment

    # ── 管理员审核 ────────────────────────────────────────

    def approve_payment(
        self,
        payment_id: int,
        admin_id: int,
        db: Session,
        referral_code: str | None = None,
    ) -> Payment:
        """管理员线下审核通过。

        管理员可手动填写推荐码（如果支付时未提供）。
        """
        payment = self._get_payment(payment_id, db, for_update=True)
        if not payment:
            raise ValueError("支付订单不存在")

        if payment.status != "pending":
            raise ValueError("支付订单已处理")

        # 管理员可手动填写推荐码
        if referral_code and not payment.referral_code:
            result = self._referral_service.validate_referral_code(
                referral_code, db
            )
            if not result["valid"]:
                raise ValueError("推荐码无效")
            # 自我推荐检查
            referrer_id = result["user_id"]
            existing_user = db.query(User).filter(User.email == payment.email).first()
            if existing_user and existing_user.id == referrer_id:
                raise ValueError("不能使用自己的推荐码")
            payment.referral_code = referral_code

        # 处理支付成功逻辑
        self._process_payment_success(payment, db)

        # 更新支付记录
        payment.status = "paid"
        payment.channel = "offline"
        payment.reviewed_by = admin_id
        payment.reviewed_at = datetime.now(timezone.utc)
        payment.pending_user_key = None

        AuditService.log(
            action="payment_approve",
            operator_type="admin",
            target_type="payment",
            target_id=payment.id,
            old_value={"status": "pending"},
            new_value={"status": "paid", "channel": "offline"},
            business_id=f"payment_{payment.id}",
            db=db,
            operator_id=admin_id,
        )

        # 通知用户
        if payment.user_id:
            from app.services.notification_service import NotificationService
            NotificationService.notify_payment_approved(
                user_id=payment.user_id,
                amount=str(int(payment.amount)),
                new_role=payment.target_role,
                db=db,
            )

        db.commit()
        db.refresh(payment)
        logger.info(
            "Payment approved: payment_id=%d admin_id=%d", payment.id, admin_id
        )
        return payment

    def reject_payment(
        self, payment_id: int, admin_id: int, reason: str, db: Session
    ) -> Payment:
        """拒绝支付申请。"""
        payment = self._get_payment(payment_id, db, for_update=True)
        if not payment:
            raise ValueError("支付订单不存在")

        if payment.status != "pending":
            raise ValueError("支付订单已处理")

        payment.status = "failed"
        payment.reject_reason = reason
        payment.reviewed_by = admin_id
        payment.reviewed_at = datetime.now(timezone.utc)
        payment.pending_user_key = None

        AuditService.log(
            action="payment_reject",
            operator_type="admin",
            target_type="payment",
            target_id=payment.id,
            old_value={"status": "pending"},
            new_value={"status": "failed", "reject_reason": reason},
            business_id=f"payment_{payment.id}",
            db=db,
        )

        db.commit()
        db.refresh(payment)
        logger.info(
            "Payment rejected: payment_id=%d reason=%s", payment.id, reason
        )
        return payment

    # ── 查询 ──────────────────────────────────────────────

    def get_payment_status(self, payment_id: int, db: Session) -> dict:
        """查询支付状态。"""
        payment = self._get_payment(payment_id, db)
        if not payment:
            raise ValueError("支付订单不存在")
        return {
            "payment_id": payment.id,
            "status": payment.status,
            "amount": str(payment.amount),
            "target_role": payment.target_role,
            "license_code": payment.license_code,
            "redirect_url": payment.redirect_url,
        }

    def list_user_payments(self, user_id: int, db: Session) -> list[Payment]:
        """列出用户的支付记录，按创建时间倒序。"""
        return (
            db.query(Payment)
            .filter(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .all()
        )

    def list_payments(
        self, db: Session, status: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Payment], int]:
        """管理员查看支付记录列表，支持状态筛选和分页。"""
        query = db.query(Payment)
        if status:
            query = query.filter(Payment.status == status)
        total = query.count()
        records = (
            query.order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return records, total


def get_payment_service() -> PaymentService:
    return PaymentService()
