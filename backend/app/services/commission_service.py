import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.payment import Payment
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

from app.core.constants import VALID_PAYMENT_AMOUNTS, ROLE_LEVEL


def record_commission(
    user_id: int,
    amount: Decimal,
    commission_type: str,
    source_user_id: int | None,
    business_id: str,
    db: Session,
) -> CommissionRecord | None:
    """Record a commission with idempotency protection.

    Returns the CommissionRecord if created, None if already exists.

    幂等保证：先查 existing，命中则返回 None。并发下两事务同时未查到时，第二个
    flush 撞 business_id UNIQUE 抛 IntegrityError，捕获后 rollback 并返回 None
    （幂等降级）。该并发路径在当前唯一生产调用方 process_payment 不可达（其用
    for_update 锁 Payment 序列化、business_id 按 payment_id 唯一）；此 except
    为防御性兜底，触发时调用方事务需重试。
    """
    existing = (
        db.query(CommissionRecord)
        .filter(CommissionRecord.business_id == business_id)
        .first()
    )
    if existing:
        logger.info(
            "Commission already recorded: business_id=%s", business_id
        )
        return None

    record = CommissionRecord(
        user_id=user_id,
        amount=amount,
        type=commission_type,
        source_user_id=source_user_id,
        business_id=business_id,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        # F4: 并发竞态——另一事务已插入同 business_id，UNIQUE 约束兜底。
        # 使用 savepoint 回滚，不影响外层事务。
        db.rollback()
        logger.info(
            "Commission race resolved (idempotent): business_id=%s", business_id
        )
        return None

    AuditService.log(
        action="commission_create",
        operator_type="system",
        target_type="commission_record",
        target_id=record.id,
        old_value=None,
        new_value={
            "user_id": user_id,
            "amount": str(amount),
            "type": commission_type,
            "source_user_id": source_user_id,
            "business_id": business_id,
        },
        business_id=business_id,
        db=db,
    )

    # Story 5.2: 通知用户佣金入账
    from app.services.notification_service import NotificationService
    NotificationService.notify_commission_credited(
        user_id=user_id,
        amount=str(amount),
        commission_type=commission_type,
        db=db,
    )

    logger.info(
        "Commission recorded: user_id=%d amount=%s type=%s business_id=%s",
        user_id,
        amount,
        commission_type,
        business_id,
    )
    return record


class CommissionEngine:
    """Commission calculation and recording engine.

    场景 A（额度销售）不产生佣金，不经过本引擎。
    场景 B（推荐支付）产生佣金，由本引擎计算和记账。

    事务约定：本引擎所有写操作只 flush 不 commit。调用方（Story 3.x 支付确认
    流程）必须在同一事务内、process_payment 返回后负责 commit，否则佣金记录
    会随 session 关闭而回滚（静默丢失）。详见 process_payment docstring。
    """

    def __init__(self, db: Session):
        self.db = db

    # ── 配置查询 ──────────────────────────────────────────

    def get_config(self, role: str, scene: str) -> CommissionConfig | None:
        """从数据库读取佣金配置。配置不存在返回 None（由调用方判断）。"""
        return (
            self.db.query(CommissionConfig)
            .filter(
                CommissionConfig.role == role,
                CommissionConfig.scene == scene,
            )
            .first()
        )

    # ── 场景 B：首次奖励 ─────────────────────────────────

    def calculate_first_reward(
        self, referrer_user_id: int, payment_amount: int, payment_id: int,
        source_user_id: int | None = None,
    ) -> dict | None:
        """计算场景 B 首次奖励。

        Args:
            referrer_user_id: 推荐人用户 ID
            payment_amount: 支付金额（888/5000/10000）
            payment_id: 支付记录 ID（用于生成 business_id）
            source_user_id: 触发本次支付的用户 ID（即支付者），
                            写入 CommissionRecord.source_user_id，用于收益明细展示来源。
                            888 支付时为 None（无关联用户）。

        Returns:
            dict with keys: user_id, amount(Decimal), commission_type,
            business_id, source_user_id
            None if no config found
        """
        referrer = self.db.query(User).filter(User.id == referrer_user_id).first()
        if not referrer:
            return None

        scene = f"first_reward_{payment_amount}"
        config = self.get_config(role=referrer.role, scene=scene)
        if not config:
            logger.info(
                "无首次奖励: 推荐人角色=%s scene=%s（配置不存在或推荐人不存在）",
                referrer.role,
                scene,
            )
            return None

        return {
            "user_id": referrer_user_id,
            "amount": Decimal(config.reward_value),
            "commission_type": "first_reward",
            "business_id": f"payment_{payment_id}",
            "source_user_id": source_user_id,
        }

    # ── 场景 B：后续收益 ─────────────────────────────────

    def calculate_followup_reward(
        self, payment_id: int, referrer_user_id: int,
        source_user_id: int | None = None,
    ) -> dict | None:
        """计算后续收益：代理从经销商的推荐支付中获得 133.2 元/笔。

        由 referral_code 反查推荐人（经销商），再查经销商的上级（代理）：
            支付(referral_code) → 推荐人(B=distributor) → B.parent(A=agent)
        仅当支付金额==888、B 是经销商、A 是代理时才计算。

        Args:
            payment_id: 支付记录 ID
            referrer_user_id: 推荐人（经销商 B）的用户 ID
            source_user_id: 支付者用户 ID（888 时为 None）

        Returns:
            dict with keys: user_id(代理A), amount(Decimal), commission_type,
            business_id, source_user_id
            None if 条件不满足
        """
        referrer = self.db.query(User).filter(
            User.id == referrer_user_id
        ).first()
        if not referrer or referrer.role != "distributor" or not referrer.parent_id:
            return None

        agent = self.db.query(User).filter(
            User.id == referrer.parent_id
        ).first()
        if not agent or agent.role != "agent":
            return None

        config = self.get_config(role="agent", scene="followup_reward")
        if not config:
            return None

        return {
            "user_id": agent.id,
            "amount": Decimal(config.reward_value),
            "commission_type": "followup_reward",
            "business_id": f"payment_{payment_id}_followup_{agent.id}",
            "source_user_id": source_user_id,
        }

    # ── 长期奖励（Epic 5 Story 5.1） ─────────────────────

    def calculate_long_term_reward(
        self, user_id: int, period: str, db: Session | None = None
    ) -> list[CommissionRecord]:
        """计算并记账长期奖励（团队奖金）。

        对指定用户，统计其**直接下级**在上一结算周期的总佣金收入，
        按用户自身角色的 team_bonus 比例记账。

        规则：
        - 代理(5%): 从所有直接下级（含经销商）的佣金中提取，但代理→经销商对
          已由 133.2 元/笔 followup_reward 覆盖，故排除经销商下级。
        - 经销商(4%): 从所有直接下级的佣金中提取。

        幂等：business_id = "settle_{user_id}_{period}"

        Args:
            user_id: 被结算的用户 ID
            period: 结算周期标识 (YYYYMM)
            db: 数据库 session（若 None 则使用 self.db）

        Returns:
            新创建的 CommissionRecord 列表（已存在则跳过，返回空列表）
        """
        session = db or self.db
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 仅代理/经销商有长期奖励
        if user.role not in ("agent", "distributor"):
            return []

        # 查配置
        config = self.get_config(user.role, "team_bonus")
        if not config or config.reward_type != "percentage":
            logger.warning("No team_bonus config for role=%s", user.role)
            return []

        ratio = Decimal(str(config.reward_value))
        business_id = f"settle_{user_id}_{period}"

        # 幂等检查
        existing = (
            session.query(CommissionRecord)
            .filter(CommissionRecord.business_id == business_id)
            .first()
        )
        if existing:
            logger.info("Long-term reward already settled: %s", business_id)
            return []

        # 查直接下级
        children = (
            session.query(User)
            .filter(User.parent_id == user_id)
            .all()
        )
        if not children:
            return []

        # 代理排除经销商下级（已由 followup_reward 覆盖）
        if user.role == "agent":
            children = [c for c in children if c.role != "distributor"]

        if not children:
            return []

        # 聚合直接下级在上一周期的总佣金
        year = int(period[:4])
        month = int(period[4:6])
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        period_start = datetime(prev_year, prev_month, 1, tzinfo=timezone.utc)
        if prev_month == 12:
            period_end = datetime(prev_year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(prev_year, prev_month + 1, 1, tzinfo=timezone.utc)

        child_ids = [c.id for c in children]
        total_child_income = (
            session.query(func.coalesce(func.sum(CommissionRecord.amount), 0))
            .filter(
                CommissionRecord.user_id.in_(child_ids),
                CommissionRecord.created_at >= period_start,
                CommissionRecord.created_at < period_end,
            )
            .scalar()
        )
        total_child_income = Decimal(str(total_child_income))

        if total_child_income <= 0:
            return []

        reward_amount = (total_child_income * ratio).quantize(Decimal("0.01"))

        if reward_amount <= 0:
            return []

        record = record_commission(
            user_id=user_id,
            amount=reward_amount,
            commission_type="team_bonus",
            source_user_id=None,
            business_id=business_id,
            db=session,
        )

        if record:
            logger.info(
                "Long-term reward settled: user_id=%d period=%s children=%d "
                "child_income=%s ratio=%s reward=%s",
                user_id, period, len(child_ids),
                total_child_income, ratio, reward_amount,
            )
            return [record]
        return []

    # ── 集成方法：支付确认后处理 ─────────────────────────

    def process_payment(
        self,
        payment_id: int,
    ) -> list[CommissionRecord]:
        """支付确认后的佣金处理。

        处理两类佣金：
        1. 首次奖励：推荐人的直接上级获得（2 角色 × 3 金额查表）。
        2. 后续收益：仅当支付金额==888 且 推荐人是经销商、经销商上级是代理
           时触发，代理获得 133.2 元/笔。

        无推荐码 = 不产生佣金。

        Args:
            payment_id: 支付记录 ID

        Returns:
            已创建的 CommissionRecord 列表（可能为空）。

        ⚠️ 事务约定（C1）：本方法只 flush 不 commit。调用方必须在同一事务内
        于本方法返回后调用 db.commit()，否则佣金记录随 session 关闭回滚丢失。
        """
        records: list[CommissionRecord] = []

        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            logger.warning("支付记录不存在: payment_id=%d", payment_id)
            return records

        amount = int(payment.amount)

        # C9: amount 必须是 int，防 888.0(float) 过 in 校验但破坏 scene 查表
        if not isinstance(amount, int) or isinstance(amount, bool):
            logger.warning("非法支付金额类型: amount=%r, 跳过佣金记账", amount)
            return records

        # SF-1: 校验金额合法性
        if amount not in VALID_PAYMENT_AMOUNTS:
            logger.warning("非法支付金额: amount=%d, 跳过佣金记账", amount)
            return records

        # 无推荐码 = 不产生佣金
        if not payment.referral_code:
            logger.info("无推荐码，跳过佣金记账: payment_id=%d", payment_id)
            return records

        # 验证推荐码，获取推荐人
        from app.services.referral_service import ReferralService
        referral_service = ReferralService()
        result = referral_service.validate_referral_code(
            payment.referral_code, self.db
        )
        if not result["valid"]:
            logger.warning(
                "推荐码无效，跳过佣金记账: payment_id=%d code=%s",
                payment_id, payment.referral_code,
            )
            return records

        referrer_user_id = result["user_id"]
        source_user_id = payment.user_id  # 888 为 None，5000/10000 为新用户 ID

        # ── 首次奖励：推荐人获得 ──
        reward = self.calculate_first_reward(
            referrer_user_id=referrer_user_id,
            payment_amount=amount,
            payment_id=payment_id,
            source_user_id=source_user_id,
        )

        if reward:
            record = self.record(
                user_id=reward["user_id"],
                amount=reward["amount"],
                commission_type=reward["commission_type"],
                source_user_id=reward["source_user_id"],
                business_id=reward["business_id"],
            )
            if record:
                records.append(record)
                logger.info(
                    "首次奖励已记账: 推荐人=%d 金额=%s business_id=%s",
                    reward["user_id"],
                    reward["amount"],
                    reward["business_id"],
                )
        else:
            logger.info(
                "无首次奖励: 支付ID=%d 支付金额=%d（推荐人角色无对应配置）",
                payment_id,
                amount,
            )

        # ── 后续收益：仅支付 888 时触发链路检查 ──
        if amount == 888:
            followup = self.calculate_followup_reward(
                payment_id=payment_id,
                referrer_user_id=referrer_user_id,
                source_user_id=source_user_id,
            )
            if followup:
                record = self.record(
                    user_id=followup["user_id"],
                    amount=followup["amount"],
                    commission_type=followup["commission_type"],
                    source_user_id=followup["source_user_id"],
                    business_id=followup["business_id"],
                )
                if record:
                    records.append(record)
                    logger.info(
                        "后续收益已记账: 代理=%d 金额=%s business_id=%s",
                        followup["user_id"],
                        followup["amount"],
                        followup["business_id"],
                    )

        return records

    # ── 记账（保持不变） ─────────────────────────────────

    def record(
        self,
        user_id: int,
        amount: Decimal,
        commission_type: str,
        source_user_id: int | None,
        business_id: str,
    ) -> CommissionRecord | None:
        """Record a commission with idempotency protection."""
        return record_commission(
            user_id=user_id,
            amount=amount,
            commission_type=commission_type,
            source_user_id=source_user_id,
            business_id=business_id,
            db=self.db,
        )

    def log_audit(
        self,
        action: str,
        target_type: str,
        target_id: int,
        old_value: dict | None,
        new_value: dict | None,
        business_id: str,
    ) -> None:
        """Write an audit log entry."""
        AuditService.log(
            action=action,
            operator_type="system",
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            business_id=business_id,
            db=self.db,
        )
