from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.core.database import Base


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    activated_user_id = Column(String(128), nullable=True)
    activated_user_info = Column(String(512), nullable=True)
    source = Column(
        Enum("payment", "sale", "role_builtin", name="license_source"),
        nullable=False,
    )
    source_id = Column(Integer, nullable=True)
    status = Column(
        Enum("unused", "activated", "expired", name="license_status"),
        server_default="unused",
        nullable=False,
    )
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    key_version = Column(Integer, server_default="1", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
