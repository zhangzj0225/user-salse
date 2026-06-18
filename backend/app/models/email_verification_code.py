from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, func, text

from app.core.database import Base


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(128), nullable=False)
    code = Column(String(6), nullable=False)
    scene = Column(String(32), server_default="register", nullable=False)
    verified = Column(Boolean, server_default=text("false"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_email_scene_verified", "email", "scene", "verified", "expires_at"),
    )
