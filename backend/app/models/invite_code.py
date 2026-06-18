from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    generator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_version = Column(Integer, server_default="1", nullable=False)
    used_by = Column(Integer, nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
