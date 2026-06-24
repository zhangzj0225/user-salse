"""业务常量 — 单一数据源，避免跨模块重复定义。

所有硬编码的配置值集中在此文件。生产环境通过 SystemConfig / .env 覆盖。
"""

# ═══════════════════════════════════════════════════════════
# 支付金额 & 角色映射
# ═══════════════════════════════════════════════════════════

VALID_PAYMENT_AMOUNTS = (888, 5000, 10000)

# 888 支付不改变用户角色，仅生成 License 供外部业务系统激活。
# "member_license" 是 Payment.target_role 的内部标记，非用户角色（用户角色仅 distributor/agent）。
AMOUNT_ROLE_MAP = {
    888: "member_license",
    5000: "distributor",
    10000: "agent",
}

AMOUNT_QUOTA_MAP = {
    888: 0,
    5000: 11,
    10000: 22,
}

# ═══════════════════════════════════════════════════════════
# 角色层级（数值越大权限越高，防止角色降级）
# ═══════════════════════════════════════════════════════════

ROLE_LEVEL = {
    "distributor": 1,
    "agent": 2,
}

# ═══════════════════════════════════════════════════════════
# 分页
# ═══════════════════════════════════════════════════════════

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# ═══════════════════════════════════════════════════════════
# 佣金相关
# ═══════════════════════════════════════════════════════════

# 可参与长期奖励的角色
SETTLEMENT_ELIGIBLE_ROLES = ("agent", "distributor")

# 可销售额度的角色
QUOTA_ELIGIBLE_ROLES = ("agent", "distributor")

from decimal import Decimal
from sqlalchemy.orm import Session

def get_valid_payment_amounts(db: Session) -> tuple[int, ...]:
    """从 SystemConfig 读取支付金额，fallback 到默认值。"""
    try:
        from app.models.system_config import SystemConfig
        amounts = []
        for key, default in (("payment_amount_888", 888), ("payment_amount_5000", 5000), ("payment_amount_10000", 10000)):
            config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
            amounts.append(int(Decimal(config.config_value)) if config else default)
        return tuple(amounts)
    except Exception:
        return VALID_PAYMENT_AMOUNTS

def get_amount_quota_map(db: Session) -> dict[int, int]:
    """从 SystemConfig 读取额度映射。"""
    try:
        from app.models.system_config import SystemConfig
        agent_config = db.query(SystemConfig).filter(SystemConfig.config_key == "quota_for_agent").first()
        dist_config = db.query(SystemConfig).filter(SystemConfig.config_key == "quota_for_distributor").first()
        agent_quota = int(agent_config.config_value) if agent_config else 22
        dist_quota = int(dist_config.config_value) if dist_config else 11
        return {888: 0, 5000: dist_quota, 10000: agent_quota}
    except Exception:
        return AMOUNT_QUOTA_MAP

def get_settlement_cycle(db: Session) -> str:
    """读取结算周期类型: monthly/weekly/daily。"""
    try:
        from app.models.system_config import SystemConfig
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "settlement_cycle").first()
        return config.config_value if config else "monthly"
    except Exception:
        return "monthly"
