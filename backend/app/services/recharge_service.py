"""充值服务。"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.recharge import Recharge
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.commission_service import CommissionEngine
from app.services.license_service import LicenseService

logger = logging.getLogger(__name__)

VALID_RECHARGE_AMOUNTS = (888, 5000, 10000)

AMOUNT_ROLE_MAP = {
    888: "member",
    5000: "distributor",
    10000: "agent",
}

AMOUNT_QUOTA_MAP = {
    888: 0,
    5000: 11,
    10000: 22,
}

# 角色等级（用于 BH-3：充值后取已购最高档，而非覆盖式赋值，避免降级）
# PRD「各充值独立不互斥」—— 充 10000 后再充 888 不应把代理降级为会员
ROLE_LEVEL = {"user": 0, "member": 1, "distributor": 2, "agent": 3}


def _higher_role(current: str, candidate: str) -> str:
    """返回两个角色中等级更高者，保证充值只升不降。"""
    if ROLE_LEVEL.get(candidate, 0) > ROLE_LEVEL.get(current, 0):
        return candidate
    return current


class RechargeService:
    """充值申请、审核服务。"""

    def __init__(self):
        self._license_service = LicenseService()

    def _get_recharge(self, recharge_id: int, db: Session, *, for_update: bool = False) -> Recharge | None:
        """查询充值记录，可选行锁。"""
        query = db.query(Recharge).filter(Recharge.id == recharge_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def create_recharge(self, user_id: int, amount: int, db: Session) -> Recharge:
        """创建充值申请。"""
        if amount not in VALID_RECHARGE_AMOUNTS:
            raise ValueError(f"充值金额必须为 {VALID_RECHARGE_AMOUNTS} 之一")

        # BH-5: 同用户已有 pending 充值时不允许新建，防止多笔 pending 并发审批
        # 触发 lost update（F5）与角色非确定性。
        existing_pending = (
            db.query(Recharge)
            .filter(Recharge.user_id == user_id, Recharge.status == "pending")
            .first()
        )
        if existing_pending:
            raise ValueError("已有待审核的充值申请，请等待审核完成")

        recharge = Recharge(
            user_id=user_id,
            amount=amount,
            target_role=AMOUNT_ROLE_MAP[amount],
            status="pending",
        )
        db.add(recharge)
        db.commit()
        db.refresh(recharge)
        logger.info(
            "Recharge created: user_id=%d amount=%d target_role=%s recharge_id=%d",
            user_id, amount, recharge.target_role, recharge.id,
        )
        return recharge

    def approve_recharge(self, recharge_id: int, admin_id: int, db: Session) -> Recharge:
        """批准充值申请。"""
        # M2: 行锁防止并发批准
        recharge = self._get_recharge(recharge_id, db, for_update=True)
        if not recharge:
            raise ValueError("充值记录不存在")

        if recharge.status != "pending":
            raise ValueError("充值已处理")

        # F5: 锁 User 行，防止并发审批同一用户多笔充值导致 role/quota lost update
        user = (
            db.query(User)
            .filter(User.id == recharge.user_id)
            .with_for_update()
            .first()
        )
        if not user:
            raise ValueError("充值用户不存在")

        amount = int(recharge.amount)
        old_role = user.role
        old_quota = user.account_quota

        # BH-3: 角色取已购最高档（只升不降），非覆盖式赋值。
        # PRD「各充值独立不互斥」—— agent 再充 888 不应降级为 member 丧失代理身份与额度。
        user.role = _higher_role(user.role, AMOUNT_ROLE_MAP[amount])
        # 额度累加
        user.account_quota += AMOUNT_QUOTA_MAP[amount]

        # 更新充值记录
        recharge.status = "approved"
        recharge.reviewed_by = admin_id
        recharge.reviewed_at = datetime.now(timezone.utc)

        # License 生成（stub）
        self._license_service.generate_for_recharge(
            user_id=user.id,
            email=user.email,
            recharge_id=recharge.id,
            target_role=user.role,
            db=db,
        )

        # 佣金记账（只 flush 不 commit，由本方法末尾统一 commit）
        # S3: 异常会回滚整个事务（角色+额度+状态全部回滚），符合"全成功或全失败"语义
        engine = CommissionEngine(db)
        engine.process_recharge(
            recharge_id=recharge.id,
            recharger_user_id=user.id,
            amount=amount,
        )

        # 审计日志（只 flush 不 commit）
        AuditService.log(
            action="recharge_approve",
            operator_type="admin",
            target_type="recharge",
            target_id=recharge.id,
            old_value={"role": old_role, "quota": old_quota, "status": "pending"},
            new_value={"role": user.role, "quota": user.account_quota, "status": "approved"},
            business_id=f"recharge_{recharge.id}",
            db=db,
        )

        db.commit()
        db.refresh(recharge)
        logger.info(
            "Recharge approved: recharge_id=%d user_id=%d role=%s quota=%d",
            recharge.id, user.id, user.role, user.account_quota,
        )
        return recharge

    def reject_recharge(
        self, recharge_id: int, admin_id: int, reason: str, db: Session
    ) -> Recharge:
        """拒绝充值申请。"""
        # M2: 行锁防止并发拒绝
        recharge = self._get_recharge(recharge_id, db, for_update=True)
        if not recharge:
            raise ValueError("充值记录不存在")

        if recharge.status != "pending":
            raise ValueError("充值已处理")

        recharge.status = "rejected"
        recharge.reject_reason = reason
        recharge.reviewed_by = admin_id
        recharge.reviewed_at = datetime.now(timezone.utc)

        AuditService.log(
            action="recharge_reject",
            operator_type="admin",
            target_type="recharge",
            target_id=recharge.id,
            old_value={"status": "pending"},
            new_value={"status": "rejected", "reject_reason": reason},
            business_id=f"recharge_{recharge.id}",
            db=db,
        )

        db.commit()
        db.refresh(recharge)
        logger.info(
            "Recharge rejected: recharge_id=%d reason=%s", recharge.id, reason
        )
        return recharge

    def list_user_recharges(self, user_id: int, db: Session) -> list[Recharge]:
        """列出用户的充值记录，按创建时间倒序。"""
        return (
            db.query(Recharge)
            .filter(Recharge.user_id == user_id)
            .order_by(Recharge.created_at.desc())
            .all()
        )

    def list_recharges(
        self, db: Session, status: str | None = None
    ) -> list[Recharge]:
        """管理员查看充值记录列表，支持状态筛选。"""
        query = db.query(Recharge)
        if status:
            query = query.filter(Recharge.status == status)
        return query.order_by(Recharge.created_at.desc()).all()


def get_recharge_service() -> RechargeService:
    return RechargeService()
