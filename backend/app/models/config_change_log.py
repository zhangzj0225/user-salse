from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ConfigChangeLog(Base):
    __tablename__ = "config_change_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    config_key = Column(String(64), nullable=False)
    old_value = Column(String(256), nullable=True)
    new_value = Column(String(256), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
