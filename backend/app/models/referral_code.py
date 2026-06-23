from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)  # 1人1码
    key_version = Column(Integer, server_default="1", nullable=False)
    is_active = Column(Integer, server_default="1", nullable=False)  # 是否有效（可停用）
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
