from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, func, text

from app.core.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String(32), nullable=False)
    content = Column(JSON, nullable=True)
    sent = Column(Boolean, server_default=text("false"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
