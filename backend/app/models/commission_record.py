from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Enum, ForeignKey, Integer, String, func

from app.core.database import Base


class CommissionRecord(Base):
    __tablename__ = "commission_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    type = Column(
        Enum("first_reward", "sale_commission", "team_bonus", "recommend"),
        nullable=False,
    )
    source_user_id = Column(Integer, nullable=True)
    business_id = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
