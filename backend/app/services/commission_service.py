import logging

from sqlalchemy.orm import Session

from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def record_commission(
    user_id: int,
    amount: float,
    commission_type: str,
    source_user_id: int | None,
    business_id: str,
    db: Session,
) -> CommissionRecord | None:
    """Record a commission with idempotency protection.

    Returns the CommissionRecord if created, None if already exists.
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
    db.flush()

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
        "Commission recorded: user_id=%d amount=%.2f type=%s business_id=%s",
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
        self, parent_user_id: int, recharge_amount: int, recharge_id: int
    ) -> dict | None:
        """计算场景 B 首次奖励。

        Args:
            parent_user_id: 上级用户 ID
            recharge_amount: 充值金额（888/5000/10000）
            recharge_id: 充值记录 ID（用于生成 business_id）

        Returns:
            dict with keys: user_id, amount, commission_type, business_id, source_user_id
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
            "amount": float(config.reward_value),
            "commission_type": "first_reward",
            "business_id": f"recharge_{recharge_id}",
            "source_user_id": None,  # 由 process_recharge 设置
        }

    # ── 场景 B：后续收益 ─────────────────────────────────

    def calculate_followup_reward(
        self, agent_id: int, distributor_id: int, recharge_id: int
    ) -> dict | None:
        """计算后续收益：代理从经销商的下级充值中获得 133.2 元/笔。

        仅当 agent_id 的角色是代理、distributor_id 的角色是经销商时才计算。

        Args:
            agent_id: 代理用户 ID（上级的上级）
            distributor_id: 经销商用户 ID（直接上级）
            recharge_id: 下下级充值记录 ID

        Returns:
            dict with keys: user_id, amount, commission_type, business_id
            None if条件不满足
        """
        agent = self.db.query(User).filter(User.id == agent_id).first()
        distributor = self.db.query(User).filter(User.id == distributor_id).first()

        if not agent or not distributor:
            return None
        if agent.role != "agent" or distributor.role != "distributor":
            return None

        config = self.get_config(role="agent", scene="followup_reward")
        if not config:
            return None

        return {
            "user_id": agent_id,
            "amount": float(config.reward_value),
            "commission_type": "followup_reward",
            "business_id": f"recharge_{recharge_id}_followup_{agent_id}",
            "source_user_id": distributor_id,
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

        只处理首次奖励（直接上级获得）。
        后续收益由 Story 3.8 在经销商的下级充值时调用 calculate_followup_reward()。

        ⚠️ 调用方必须确保 amount 与 recharge_id 对应的充值记录一致。

        Args:
            recharge_id: 充值记录 ID
            recharger_user_id: 充值人用户 ID
            amount: 充值金额（必须是 888/5000/10000）

        Returns:
            已创建的 CommissionRecord 列表（可能为空）
        """
        records: list[CommissionRecord] = []

        # SF-1: 校验金额合法性
        if amount not in (888, 5000, 10000):
            logger.warning("非法充值金额: amount=%d, 跳过佣金记账", amount)
            return records

        recharger = self.db.query(User).filter(User.id == recharger_user_id).first()
        if not recharger:
            logger.warning("充值用户不存在: user_id=%d", recharger_user_id)
            return records

        # 无上级，跳过所有佣金记账
        if not recharger.parent_id:
            logger.info("用户无上级，跳过佣金记账: user_id=%d", recharger_user_id)
            return records

        # 计算首次奖励
        reward = self.calculate_first_reward(
            parent_user_id=recharger.parent_id,
            recharge_amount=amount,
            recharge_id=recharge_id,
        )

        if reward:
            record = self.record(
                user_id=reward["user_id"],
                amount=reward["amount"],
                commission_type=reward["commission_type"],
                source_user_id=recharger_user_id,
                business_id=reward["business_id"],
            )
            if record:
                records.append(record)
                logger.info(
                    "首次奖励已记账: 上级=%d 金额=%.2f business_id=%s",
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

        return records

    # ── 记账（保持不变） ─────────────────────────────────

    def record(
        self,
        user_id: int,
        amount: float,
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
