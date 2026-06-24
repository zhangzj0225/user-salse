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
    "settlement_cycle": ("monthly", "结算周期(monthly/weekly/daily)", "string"),
    "settlement_cycle_days": ("30", "结算周期天数", "int"),
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


# ═════════════════════════════════════════════════════════════
# 动态配置读取工具（带 fallback 到 constants.py 硬编码默认值）
# ═════════════════════════════════════════════════════════════

def _get_config_value(db: Session, key: str, default: str | None = None) -> str | None:
    """从 SystemConfig 表读取单个配置项，不存在时返回 default。"""
    try:
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if config and config.config_value is not None:
            return config.config_value
    except Exception:
        pass
    return default


def get_dynamic_payment_configs(db: Session) -> dict:
    """动态读取支付相关配置，fallback 到 constants.py 硬编码默认值。

    Returns:
        {
            "valid_amounts": set[int],       # 有效支付金额集合
            "amount_role_map": dict,          # {金额: target_role}
            "role_quota_map": dict,           # {"agent": 配额, "distributor": 配额}
        }
    """
    # ── 1. 读取金额配置 ──
    # 配置 key → 对应 target_role 的映射
    _AMOUNT_KEY_ROLE_MAP = {
        "payment_amount_888": "member_license",
        "payment_amount_5000": "distributor",
        "payment_amount_10000": "agent",
    }

    amount_role_map: dict[int, str] = {}
    for key, role in _AMOUNT_KEY_ROLE_MAP.items():
        val_str = _get_config_value(db, key)
        if val_str is not None:
            try:
                amount_role_map[int(val_str)] = role
            except (ValueError, TypeError):
                logger.warning(
                    "SystemConfig key '%s' value '%s' 无法转为整数，跳过",
                    key, val_str,
                )

    if amount_role_map:
        logger.info(
            "使用 SystemConfig 动态支付金额: %s",
            {a: r for a, r in amount_role_map.items()},
        )
    else:
        from app.core.constants import AMOUNT_ROLE_MAP as _FALLBACK_AMOUNT_ROLE
        amount_role_map = dict(_FALLBACK_AMOUNT_ROLE)
        logger.warning(
            "SystemConfig 中未找到有效支付金额配置，fallback 到 constants.py: %s",
            set(amount_role_map.keys()),
        )

    valid_amounts = set(amount_role_map.keys())

    # ── 2. 读取额度配置 ──
    _ROLE_QUOTA_KEYS = {
        "agent": "quota_for_agent",
        "distributor": "quota_for_distributor",
    }

    role_quota_map: dict[str, int] = {}
    for role, key in _ROLE_QUOTA_KEYS.items():
        val_str = _get_config_value(db, key)
        if val_str is not None:
            try:
                role_quota_map[role] = int(val_str)
            except (ValueError, TypeError):
                logger.warning(
                    "SystemConfig key '%s' value '%s' 无法转为整数，跳过",
                    key, val_str,
                )

    if role_quota_map:
        logger.info("使用 SystemConfig 动态额度配置: %s", role_quota_map)
    else:
        # fallback 到 constants.py 硬编码
        # AMOUNT_QUOTA_MAP 是 {金额: 配额}，需要转换: agent→22, distributor→11
        _FALLBACK_QUOTA_MAP = {"agent": 22, "distributor": 11}
        role_quota_map = dict(_FALLBACK_QUOTA_MAP)
        logger.warning(
            "SystemConfig 中未找到额度配置，fallback 到 constants.py: %s",
            role_quota_map,
        )

    return {
        "valid_amounts": valid_amounts,
        "amount_role_map": amount_role_map,
        "role_quota_map": role_quota_map,
    }
