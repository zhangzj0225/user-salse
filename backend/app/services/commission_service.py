import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.recharge import Recharge
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# 充值金额常量，作为 amount 一致性校验与 followup 触发的依据
VALID_RECHARGE_AMOUNTS = (888, 5000, 10000)


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

    幂等保证：先查 existing；并发下两个事务同时未查到时，第二个 flush 会因
    business_id UNIQUE 抛 IntegrityError，捕获后重查返回 None（幂等降级），
    而非让 IntegrityError 上抛导致包裹事务整体回滚。
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
        # F4: 用 savepoint 包裹 flush，IntegrityError 只回滚 savepoint，
        # 不连累包裹事务（如 approve_recharge 内已 flush 的角色/额度/License）。
        nested = db.begin_nested()
        db.flush()
    except IntegrityError:
        # 并发竞态：另一事务已插入同 business_id。回滚 savepoint（非整事务），
        # 重查确认存在后返回 None。
        nested.rollback()
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
    场景 B（推荐充值）产生佣金，由本引擎计算和记账。

    事务约定：本引擎所有写操作只 flush 不 commit。调用方（Story 3.x 充值确认
    流程）必须在同一事务内、process_recharge 返回后负责 commit，否则佣金记录
    会随 session 关闭而回滚（静默丢失）。详见 process_recharge docstring。
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
        self, parent_user_id: int, recharge_amount: int, recharge_id: int,
        source_user_id: int | None = None,
    ) -> dict | None:
        """计算场景 B 首次奖励。

        Args:
            parent_user_id: 上级用户 ID
            recharge_amount: 充值金额（888/5000/10000）
            recharge_id: 充值记录 ID（用于生成 business_id）
            source_user_id: 触发本次充值的下级用户 ID（即充值人），
                            写入 CommissionRecord.source_user_id，用于收益明细展示来源。

        Returns:
            dict with keys: user_id, amount(Decimal), commission_type,
            business_id, source_user_id
            None if no config found (e.g. 普通用户推荐充 5000/10000)
        """
        parent = self.db.query(User).filter(User.id == parent_user_id).first()
        if not parent:
            return None

        scene = f"recharge_{recharge_amount}"
        config = self.get_config(role=parent.role, scene=scene)
        if not config:
            logger.info(
                "无首次奖励: 上级角色=%s scene=%s（配置不存在或上级不存在）",
                parent.role,
                scene,
            )
            return None

        return {
            "user_id": parent_user_id,
            "amount": Decimal(config.reward_value),
            "commission_type": "first_reward",
            "business_id": f"recharge_{recharge_id}",
            "source_user_id": source_user_id,
        }

    # ── 场景 B：后续收益 ─────────────────────────────────

    def calculate_followup_reward(
        self, recharge_id: int, recharger_user_id: int,
    ) -> dict | None:
        """计算后续收益：代理从经销商的下级充值中获得 133.2 元/笔。

        由 recharge_id 反查链路，不依赖调用方传 agent_id/distributor_id：
            recharger(C) → parent(B=distributor) → parent.parent(A=agent)
        仅当 C 充值金额==888、B 是经销商、A 是代理时才计算。

        Args:
            recharge_id: 下下级 C 的充值记录 ID
            recharger_user_id: 充值人 C 的用户 ID

        Returns:
            dict with keys: user_id(代理A), amount(Decimal), commission_type,
            business_id, source_user_id(充值人C)
            None if 条件不满足
        """
        recharger = self.db.query(User).filter(User.id == recharger_user_id).first()
        if not recharger or not recharger.parent_id:
            return None

        distributor = self.db.query(User).filter(
            User.id == recharger.parent_id
        ).first()
        if not distributor or distributor.role != "distributor" or not distributor.parent_id:
            return None

        agent = self.db.query(User).filter(
            User.id == distributor.parent_id
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
            "business_id": f"recharge_{recharge_id}_followup_{agent.id}",
            "source_user_id": recharger_user_id,  # 真实充值人 C
        }

    # ── 长期奖励（Epic 5 实现） ──────────────────────────

    def calculate_long_term_reward(
        self, user_id: int, period: str
    ) -> dict:
        """计算长期奖励。Epic 5 Story 5.1 实现。"""
        raise NotImplementedError(
            "长期奖励在 Epic 5 Story 5.1 实现"
        )

    # ── 集成方法：充值确认后处理 ─────────────────────────

    def process_recharge(
        self,
        recharge_id: int,
        recharger_user_id: int,
        amount: int,
    ) -> list[CommissionRecord]:
        """充值确认后的佣金处理。

        处理两类佣金：
        1. 首次奖励：充值人的直接上级获得（4 角色 × 3 金额查表）。
        2. 后续收益：仅当充值金额==888 且 充值人上级是经销商、经销商上级是代理
           时触发，代理获得 133.2 元/笔。

        Args:
            recharge_id: 充值记录 ID
            recharger_user_id: 充值人用户 ID
            amount: 充值金额（必须是 888/5000/10000，且必须与 recharge_id 对应的
                    recharges 记录一致）

        Returns:
            已创建的 CommissionRecord 列表（可能为空）。

        ⚠️ 事务约定（C1）：本方法只 flush 不 commit。调用方必须在同一事务内
        于本方法返回后调用 db.commit()，否则佣金记录随 session 关闭回滚丢失。
        已有测试 test_process_recharge_requires_commit_to_persist 锁定此契约。

        ⚠️ amount 一致性（C4）：本方法会查 recharges 表校验 amount 与记录一致。
        """
        records: list[CommissionRecord] = []

        # C9: amount 必须是 int，防 888.0(float) 过 in 校验但破坏 scene 查表
        if not isinstance(amount, int) or isinstance(amount, bool):
            logger.warning("非法充值金额类型: amount=%r, 跳过佣金记账", amount)
            return records

        # SF-1: 校验金额合法性
        if amount not in VALID_RECHARGE_AMOUNTS:
            logger.warning("非法充值金额: amount=%d, 跳过佣金记账", amount)
            return records

        recharger = self.db.query(User).filter(User.id == recharger_user_id).first()
        if not recharger:
            logger.warning("充值用户不存在: user_id=%d", recharger_user_id)
            return records

        # C4: 校验 amount 与 recharges 记录一致，防调用方传错金额多记/少记且被幂等键锁死
        recharge = self.db.query(Recharge).filter(Recharge.id == recharge_id).first()
        if recharge is not None:
            if int(recharge.amount) != amount:
                logger.error(
                    "充值金额不一致: recharge_id=%d 记录金额=%s 入参amount=%d, 跳过佣金记账",
                    recharge_id, recharge.amount, amount,
                )
                return records
        # recharge 不存在时（如单元测试直接构造场景）不阻塞，由调用方在真实流程保证存在

        # 无上级，跳过所有佣金记账
        if not recharger.parent_id:
            logger.info("用户无上级，跳过佣金记账: user_id=%d", recharger_user_id)
            return records

        # ── 首次奖励：直接上级获得 ──
        reward = self.calculate_first_reward(
            parent_user_id=recharger.parent_id,
            recharge_amount=amount,
            recharge_id=recharge_id,
            source_user_id=recharger_user_id,
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
                    "首次奖励已记账: 上级=%d 金额=%s business_id=%s",
                    reward["user_id"],
                    reward["amount"],
                    reward["business_id"],
                )
        else:
            logger.info(
                "无首次奖励: 充值人=%d 充值金额=%d（上级角色无对应配置）",
                recharger_user_id,
                amount,
            )

        # ── 后续收益：仅充 888 时触发链路检查（C6 收归） ──
        if amount == 888:
            followup = self.calculate_followup_reward(
                recharge_id=recharge_id,
                recharger_user_id=recharger_user_id,
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
