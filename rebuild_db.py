"""重建数据库（测试前运行）。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("ENV", "dev")

from app.core.database import get_engine, Base, get_session_local
import app.models  # noqa: ensure all models loaded
from app.models.commission_config import CommissionConfig
from app.models.admin_user import AdminUser
from app.models.system_config import SystemConfig
import bcrypt
from decimal import Decimal

engine = get_engine()
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = get_session_local()()
db.add(AdminUser(username='admin', password_hash=bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()))
configs = [
    ('agent','first_reward_888','fixed','488.4000'),
    ('agent','first_reward_5000','fixed','2750.0000'),
    ('agent','first_reward_10000','fixed','5500.0000'),
    ('agent','followup_reward','fixed','133.2000'),
    ('agent','team_bonus','percentage','0.0500'),
    ('distributor','first_reward_888','fixed','355.2000'),
    ('distributor','first_reward_5000','fixed','2000.0000'),
    ('distributor','first_reward_10000','fixed','4000.0000'),
    ('distributor','team_bonus','percentage','0.0400'),
]
for r,s,rt,v in configs:
    db.add(CommissionConfig(role=r, scene=s, reward_type=rt, reward_value=Decimal(v)))

sys_configs = [
    ("payment_amount_888", "888", "888元支付金额"),
    ("payment_amount_5000", "5000", "5000元支付金额"),
    ("payment_amount_10000", "10000", "10000元支付金额"),
    ("quota_for_agent", "22", "代理可售额度"),
    ("quota_for_distributor", "11", "经销商可售额度"),
    ("min_withdrawal_amount", "100", "最低提现金额"),
    ("settlement_cycle_days", "30", "结算周期(天)"),
    ("followup_reward_amount", "133.2", "后续收益金额"),
]
for key, value, desc in sys_configs:
    db.add(SystemConfig(config_key=key, config_value=value, description=desc))

db.commit()
db.close()
print("Database rebuilt successfully.")
