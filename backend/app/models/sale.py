from sqlalchemy import DECIMAL, Column, DateTime, ForeignKey, Integer, String, func, text

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    customer_email = Column(String(128), nullable=False)
    amount = Column(DECIMAL(10, 2), server_default=text("888.00"), nullable=False)
    remark = Column(String(256), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
