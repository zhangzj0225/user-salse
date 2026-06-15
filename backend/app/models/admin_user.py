from sqlalchemy import Column, Integer, String, DateTime, func

from app.core.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), server_default="admin", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
