from sqlalchemy import DECIMAL, Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.core.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    payment_method = Column(String(256), nullable=False)
    status = Column(
        Enum("pending", "paid", "rejected", name="ticket_status"),
        server_default="pending",
        nullable=False,
    )
    reject_reason = Column(String(256), nullable=True)
    processed_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
