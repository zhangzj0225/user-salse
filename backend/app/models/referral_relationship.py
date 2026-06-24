"""推荐关系数据模型。

记录支付时建立的上下级推荐关系，不可修改、不可删除，
支持通过关系表追溯完整的推荐链条。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, event, func

from app.core.database import Base


class ReferralRelationship(Base):
    """推荐关系记录 —— 不可变。

    - parent_user_id: 推荐人（上级）
    - child_user_id: 被推荐人（下级），仅 5000/10000 支付时有值，888 为 NULL
    - payment_id: 建立此关系的支付记录
    """

    __tablename__ = "referral_relationships"
    __table_args__ = (
        UniqueConstraint(
            "parent_user_id", "child_user_id", "payment_id",
            name="uq_referral_relationship",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, comment="推荐人（上级）"
    )
    child_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, comment="被推荐人（下级），888 支付时为 NULL"
    )
    referral_code = Column(String(128), nullable=False, comment="使用的推荐码")
    payment_id = Column(
        Integer, ForeignKey("payments.id"), nullable=True, comment="建立关系的支付记录"
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# ── 不可变保护：禁止 UPDATE / DELETE ──────────────────────────

@event.listens_for(ReferralRelationship, "before_update")
def _prevent_referral_relationship_update(mapper, connection, target):
    raise RuntimeError(
        "ReferralRelationship records are immutable and cannot be updated."
    )


@event.listens_for(ReferralRelationship, "before_delete")
def _prevent_referral_relationship_delete(mapper, connection, target):
    raise RuntimeError(
        "ReferralRelationship records are immutable and cannot be deleted."
    )
