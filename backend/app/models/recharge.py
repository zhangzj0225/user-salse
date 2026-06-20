from sqlalchemy import DECIMAL, Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


class Recharge(Base):
    __tablename__ = "recharges"
    __table_args__ = (
        # D5: 防止同一用户同时有多笔 pending 充值（TOCTOU 防御）。
        # pending_user_key 在 status=pending 时设为 user_id，否则为 NULL。
        # UNIQUE 约束下 NULL 不冲突，故仅 pending 状态互斥。
        UniqueConstraint("pending_user_key", name="uq_recharges_pending_user"),
    )

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

    # D5: pending 时 = user_id，非 pending 时 = NULL。UNIQUE 约束保证每用户最多一笔 pending。
    pending_user_key = Column(Integer, nullable=True)
