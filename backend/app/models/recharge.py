from sqlalchemy import DECIMAL, Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.core.database import Base


class Recharge(Base):
    __tablename__ = "recharges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    target_role = Column(
        Enum("member", "distributor", "agent", name="recharge_target_role"),
        nullable=False,
    )
    status = Column(
        Enum("pending", "approved", "rejected", name="recharge_status"),
        server_default="pending",
        nullable=False,
    )
    reject_reason = Column(String(256), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
