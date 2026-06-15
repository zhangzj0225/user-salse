from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, text

from app.core.database import Base


class SmsRecord(Base):
    __tablename__ = "sms_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(11), nullable=False)
    code = Column(String(6), nullable=False)
    scene = Column(String(32), server_default="sale_verify", nullable=False)
    verified = Column(Boolean, server_default=text("false"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
