"""补购申请数据模型。

代理/经销商额度耗尽后可提交补购申请，管理员审核通过后追加额度。
"""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.core.database import Base


class QuotaReplenishment(Base):
    """补购申请记录。"""

    __tablename__ = "quota_replenishments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="申请人")
    old_quota = Column(Integer, nullable=False, comment="申请时的当前额度")
    requested_amount = Column(Integer, server_default="0", nullable=False, comment="申请追加额度，0=默认额度")
    status = Column(
        Enum("pending", "approved", "rejected", name="replenishment_status"),
        server_default="pending",
        nullable=False,
        comment="审核状态",
    )
    reject_reason = Column(String(256), nullable=True, comment="拒绝原因")
    reviewed_by = Column(
        Integer, ForeignKey("admin_users.id"), nullable=True, comment="审核管理员"
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
