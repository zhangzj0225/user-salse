from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, func, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), unique=True, nullable=True)
    phone = Column(String(11), unique=True, nullable=True)
    nickname = Column(String(64), nullable=True)
    avatar_url = Column(String(256), nullable=True)
    role = Column(
        Enum("user", "distributor", "agent", name="user_role"),
        server_default="user",
        nullable=False,
    )
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    invite_code = Column(String(32), unique=True, nullable=True)
    account_quota = Column(Integer, server_default=text("0"), nullable=False)
    account_used = Column(Integer, server_default=text("0"), nullable=False)
    status = Column(
        Enum("pending", "active", "rejected", name="user_status"),
        server_default="pending",
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    children = relationship("User", back_populates="parent", remote_side=[parent_id])
    parent = relationship("User", back_populates="children", remote_side=[id])
