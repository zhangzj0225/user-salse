"""补购申请/审核服务。

代理/经销商额度耗尽后提交补购申请，管理员审核通过后追加额度。
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.quota_replenishment import QuotaReplenishment
from app.models.user import User

logger = logging.getLogger(__name__)

# S5: 角色默认额度从 SystemConfig 动态读取（见 _get_role_default_quota）

_VALID_STATUSES = ("pending", "approved", "rejected")


class QuotaReplenishmentService:
    """补购申请/审核服务。"""

    def create_replenish_request(
        self,
        user_email: str,
        amount: int,
        db: Session,
    ) -> dict:
        """创建补购申请。

        1. 根据邮箱查找用户，校验角色为 agent/distributor
        2. amount=0 时使用角色默认额度
        3. 检查是否已有 pending 申请（防止重复提交）
        4. 记录 old_quota，创建 pending 申请
        5. 写入审计日志
        """
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise ValueError("用户不存在")

        if user.role not in ("agent", "distributor"):
            raise ValueError("仅代理和经销商可提交补购申请")

        # amount=0 时使用角色默认额度（S5: 从 SystemConfig 动态读取，fallback 到硬编码）
        if amount > 0:
            requested_amount = amount
        else:
            from app.services.system_config_service import get_dynamic_payment_configs
            configs = get_dynamic_payment_configs(db)
            requested_amount = configs["role_quota_map"].get(user.role, 0)
            logger.info(
                "补购使用默认额度: role=%s quota=%d (来源: SystemConfig)",
                user.role, requested_amount,
            )
        if requested_amount <= 0:
            raise ValueError("申请额度无效")

        # 防止重复提交 pending 申请
        existing = (
            db.query(QuotaReplenishment)
            .filter(
                QuotaReplenishment.user_id == user.id,
                QuotaReplenishment.status == "pending",
            )
            .first()
        )
        if existing:
            raise ValueError("已有待审核的补购申请，请勿重复提交")

        # 创建申请
        replenish = QuotaReplenishment(
            user_id=user.id,
            old_quota=user.account_quota,
            requested_amount=requested_amount,
            status="pending",
        )
        db.add(replenish)
        db.flush()

        # 审计日志
        audit = AuditLog(
            action="quota_replenish_create",
            target_type="quota_replenishment",
            target_id=replenish.id,
            operator_type="user",
            operator_id=user.id,
            old_value=None,
            new_value={
                "old_quota": user.account_quota,
                "requested_amount": requested_amount,
                "status": "pending",
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(replenish)

        logger.info(
            "Quota replenish request created: user_id=%d request_id=%d old_quota=%d requested=%d",
            user.id, replenish.id, replenish.old_quota, requested_amount,
        )

        return {
            "id": replenish.id,
            "user_id": replenish.user_id,
            "old_quota": replenish.old_quota,
            "requested_amount": replenish.requested_amount,
            "status": replenish.status,
            "reject_reason": replenish.reject_reason,
            "reviewed_by": replenish.reviewed_by,
            "created_at": replenish.created_at,
            "updated_at": replenish.updated_at,
        }

    def list_user_requests(
        self,
        user_id: int,
        db: Session,
        status: str | None = None,
    ) -> list[dict]:
        """用户查看自己的补购申请列表。"""
        query = db.query(QuotaReplenishment).filter(
            QuotaReplenishment.user_id == user_id
        )
        if status:
            if status not in _VALID_STATUSES:
                raise ValueError(f"无效的状态参数，允许值: {_VALID_STATUSES}")
            query = query.filter(QuotaReplenishment.status == status)

        requests = query.order_by(QuotaReplenishment.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "old_quota": r.old_quota,
                "requested_amount": r.requested_amount,
                "status": r.status,
                "reject_reason": r.reject_reason,
                "reviewed_by": r.reviewed_by,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in requests
        ]

    def list_all_requests(
        self,
        db: Session,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """管理员查看所有补购申请列表（含用户邮箱），支持分页。

        返回: (requests, total)
        """
        query = db.query(QuotaReplenishment)
        if status:
            if status not in _VALID_STATUSES:
                raise ValueError(f"无效的状态参数，允许值: {_VALID_STATUSES}")
            query = query.filter(QuotaReplenishment.status == status)

        total = query.count()
        requests = (
            query.order_by(QuotaReplenishment.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # 批量加载用户邮箱
        user_ids = {r.user_id for r in requests}
        users = {}
        if user_ids:
            user_list = db.query(User).filter(User.id.in_(user_ids)).all()
            users = {u.id: u.email for u in user_list}

        result = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_email": users.get(r.user_id, ""),
                "old_quota": r.old_quota,
                "requested_amount": r.requested_amount,
                "status": r.status,
                "reject_reason": r.reject_reason,
                "reviewed_by": r.reviewed_by,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in requests
        ]
        return result, total

    def approve_replenish(
        self,
        request_id: int,
        admin_id: int,
        db: Session,
    ) -> dict:
        """管理员批准补购申请 — 追加额度到用户账户。

        1. 行锁防并发（申请记录 + 用户记录）
        2. 校验申请状态为 pending
        3. 追加额度：user.account_quota += requested_amount
        4. 申请状态 → approved
        5. 审计日志 + 通知用户
        """
        # 行锁申请记录
        replenish = (
            db.query(QuotaReplenishment)
            .filter(QuotaReplenishment.id == request_id)
            .with_for_update()
            .first()
        )
        if not replenish:
            raise ValueError("补购申请不存在")

        if replenish.status != "pending":
            raise ValueError("补购申请已处理")

        # 行锁用户记录
        user = (
            db.query(User)
            .filter(User.id == replenish.user_id)
            .with_for_update()
            .first()
        )
        if not user:
            raise ValueError("申请人不存在")

        old_status = replenish.status
        old_user_quota = user.account_quota

        # 追加额度
        user.account_quota += replenish.requested_amount

        # 更新申请状态
        replenish.status = "approved"
        replenish.reviewed_by = admin_id

        # 审计日志
        audit = AuditLog(
            action="quota_replenish_approve",
            target_type="quota_replenishment",
            target_id=replenish.id,
            operator_type="admin",
            operator_id=admin_id,
            old_value={
                "status": old_status,
                "account_quota": old_user_quota,
            },
            new_value={
                "status": "approved",
                "account_quota": user.account_quota,
                "added_amount": replenish.requested_amount,
            },
        )
        db.add(audit)

        # 通知用户
        from app.services.notification_service import NotificationService
        NotificationService.send(
            user_id=user.id,
            event_type="quota_replenish_approved",
            content={
                "request_id": replenish.id,
                "old_quota": old_user_quota,
                "added_amount": replenish.requested_amount,
                "new_quota": user.account_quota,
            },
            db=db,
        )

        db.commit()
        db.refresh(replenish)

        logger.info(
            "Quota replenish approved: request_id=%d admin_id=%d user_id=%d "
            "old_quota=%d added=%d new_quota=%d",
            request_id, admin_id, user.id,
            old_user_quota, replenish.requested_amount, user.account_quota,
        )

        return {
            "id": replenish.id,
            "user_id": replenish.user_id,
            "old_quota": replenish.old_quota,
            "requested_amount": replenish.requested_amount,
            "status": replenish.status,
            "reviewed_by": replenish.reviewed_by,
            "reject_reason": replenish.reject_reason,
            "created_at": replenish.created_at,
            "updated_at": replenish.updated_at,
        }

    def reject_replenish(
        self,
        request_id: int,
        admin_id: int,
        reason: str,
        db: Session,
    ) -> dict:
        """管理员拒绝补购申请。

        1. 行锁防并发
        2. 校验申请状态为 pending
        3. 申请状态 → rejected，记录拒绝原因
        4. 审计日志 + 通知用户
        """
        # 行锁申请记录
        replenish = (
            db.query(QuotaReplenishment)
            .filter(QuotaReplenishment.id == request_id)
            .with_for_update()
            .first()
        )
        if not replenish:
            raise ValueError("补购申请不存在")

        if replenish.status != "pending":
            raise ValueError("补购申请已处理")

        old_status = replenish.status

        # 更新申请状态
        replenish.status = "rejected"
        replenish.reject_reason = reason
        replenish.reviewed_by = admin_id

        # 审计日志
        audit = AuditLog(
            action="quota_replenish_reject",
            target_type="quota_replenishment",
            target_id=replenish.id,
            operator_type="admin",
            operator_id=admin_id,
            old_value={"status": old_status},
            new_value={"status": "rejected", "reject_reason": reason},
        )
        db.add(audit)

        # 通知用户
        from app.services.notification_service import NotificationService
        NotificationService.send(
            user_id=replenish.user_id,
            event_type="quota_replenish_rejected",
            content={
                "request_id": replenish.id,
                "reason": reason,
            },
            db=db,
        )

        db.commit()
        db.refresh(replenish)

        logger.info(
            "Quota replenish rejected: request_id=%d admin_id=%d reason=%s",
            request_id, admin_id, reason,
        )

        return {
            "id": replenish.id,
            "user_id": replenish.user_id,
            "old_quota": replenish.old_quota,
            "requested_amount": replenish.requested_amount,
            "status": replenish.status,
            "reviewed_by": replenish.reviewed_by,
            "reject_reason": replenish.reject_reason,
            "created_at": replenish.created_at,
            "updated_at": replenish.updated_at,
        }


def get_quota_replenishment_service() -> QuotaReplenishmentService:
    """获取补购申请服务实例。"""
    return QuotaReplenishmentService()
