"""系统参数配置模型 (Story 4.4)。"""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class SystemConfig(Base):
    """系统参数配置 — key-value 存储。"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, nullable=False)
    config_value = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
