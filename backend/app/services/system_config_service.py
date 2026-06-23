"""系统参数配置服务 (Story 4.4)。"""

import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.config_change_log import ConfigChangeLog
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

# 默认配置项（应用启动时自动初始化）
DEFAULT_CONFIGS = {
    "payment_amount_888": ("888", "888元支付金额", "decimal"),
    "payment_amount_5000": ("5000", "5000元支付金额", "decimal"),
    "payment_amount_10000": ("10000", "10000元支付金额", "decimal"),
    "quota_for_agent": ("22", "代理可售额度", "int"),
    "quota_for_distributor": ("11", "经销商可售额度", "int"),
    "min_withdrawal_amount": ("100", "最低提现金额", "decimal"),
    "settlement_cycle_days": ("30", "结算周期(天)", "int"),
    "followup_reward_amount": ("133.2", "后续收益金额", "decimal"),
}

_initialized = False


class SystemConfigService:
    """系统参数配置服务。"""

    def list_configs(self, db: Session) -> list[dict]:
        """列出所有系统配置。"""
        self._ensure_defaults(db)
        configs = db.query(SystemConfig).order_by(SystemConfig.config_key).all()
        return [
            {
                "config_key": c.config_key,
                "config_value": c.config_value,
                "description": c.description,
            }
            for c in configs
        ]

    def get_config(self, key: str, db: Session) -> dict:
        """获取单个配置项。"""
        self._ensure_defaults(db)
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if not config:
            raise ValueError(f"配置项 {key} 不存在")
        return {
            "config_key": config.config_key,
            "config_value": config.config_value,
            "description": config.description,
        }

    def update_config(
        self, key: str, new_value: str, admin_id: int, db: Session
    ) -> dict:
        """更新配置项，记录变更日志。

        数值型配置会校验格式。
        """
        self._ensure_defaults(db)

        # 行锁防并发
        config = (
            db.query(SystemConfig)
            .filter(SystemConfig.config_key == key)
            .with_for_update()
            .first()
        )
        if not config:
            raise ValueError(f"配置项 {key} 不存在")

        # 数值校验
        meta = DEFAULT_CONFIGS.get(key)
        if meta and meta[2] in ("int", "decimal"):
            try:
                if meta[2] == "int":
                    val = int(new_value)
                    if val < 0:
                        raise ValueError(f"{key} 不能为负数")
                else:
                    val = Decimal(new_value)
                    if val < 0:
                        raise ValueError(f"{key} 不能为负数")
            except (ValueError, InvalidOperation):
                raise ValueError(f"配置项 {key} 需要有效的{'整数' if meta[2] == 'int' else '数值'}")

        old_value = config.config_value
        config.config_value = new_value

        log = ConfigChangeLog(
            admin_id=admin_id,
            config_key=key,
            old_value=old_value,
            new_value=new_value,
        )
        db.add(log)
        db.commit()

        logger.info(
            "Config updated: key=%s old=%s new=%s admin_id=%s",
            key, old_value, new_value, admin_id,
        )

        return {
            "config_key": config.config_key,
            "config_value": config.config_value,
            "description": config.description,
        }

    def list_change_logs(self, db: Session, limit: int = 50) -> list[dict]:
        """查看配置变更日志。"""
        logs = (
            db.query(ConfigChangeLog)
            .order_by(ConfigChangeLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "admin_id": l.admin_id,
                "config_key": l.config_key,
                "old_value": l.old_value,
                "new_value": l.new_value,
                "created_at": l.created_at,
            }
            for l in logs
        ]

    def _ensure_defaults(self, db: Session) -> None:
        """确保默认配置项存在。仅在首次调用时初始化。"""
        global _initialized
        if _initialized:
            return

        existing = {c.config_key for c in db.query(SystemConfig).all()}
        added = False
        for key, (value, desc, _) in DEFAULT_CONFIGS.items():
            if key not in existing:
                config = SystemConfig(
                    config_key=key,
                    config_value=value,
                    description=desc,
                )
                db.add(config)
                added = True
        if added:
            db.commit()
        _initialized = True


def reset_config_initialization():
    """重置初始化标志（测试用）。"""
    global _initialized
    _initialized = False


def get_system_config_service() -> SystemConfigService:
    return SystemConfigService()
