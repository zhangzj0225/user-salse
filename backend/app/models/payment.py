from sqlalchemy import DECIMAL, Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # D5: 防止同一用户同时有多笔 pending 支付（TOCTOU 防御）。
        UniqueConstraint("pending_user_key", name="uq_payments_pending_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 5000/10000支付时关联用户，888为NULL
    email = Column(String(128), nullable=False)  # 支付者邮箱
    amount = Column(DECIMAL(10, 2), nullable=False)
    target_role = Column(
        Enum("member_license", "distributor", "agent", name="payment_target_role"),
        nullable=False,
    )
    referral_code = Column(String(64), nullable=True)  # 推荐码（选填）
    channel = Column(
        Enum("online", "offline", name="payment_channel"),
        server_default="online",
        nullable=False,
    )
    status = Column(
        Enum("pending", "paid", "failed", "refunded", name="payment_status"),
        server_default="pending",
        nullable=False,
    )
    payment_no = Column(String(128), nullable=True)  # 第三方支付流水号
    license_code = Column(String(128), nullable=True)  # 支付成功后生成的License
    reviewed_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reject_reason = Column(String(256), nullable=True)
    redirect_url = Column(String(512), nullable=True)  # 支付成功回跳URL
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    pending_user_key = Column(Integer, nullable=True)  # pending时=user_id，非pending时=NULL
