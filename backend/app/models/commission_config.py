from sqlalchemy import DECIMAL, Column, DateTime, Enum, Integer, String, UniqueConstraint, func

from app.core.database import Base


class CommissionConfig(Base):
    __tablename__ = "commission_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(
        Enum("user", "member", "distributor", "agent", name="commission_role"),
        nullable=False,
    )
    scene = Column(String(32), nullable=False)
    reward_type = Column(
        Enum("fixed", "percentage", name="reward_type"),
        nullable=False,
    )
    reward_value = Column(DECIMAL(10, 4), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("role", "scene", name="uq_commission_configs_role_scene"),
    )
