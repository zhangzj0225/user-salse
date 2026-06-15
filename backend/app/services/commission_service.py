import logging

from sqlalchemy.orm import Session

from app.models.commission_record import CommissionRecord
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def record_commission(
    user_id: int,
    amount: float,
    commission_type: str,
    source_user_id: int | None,
    business_id: str,
    db: Session,
) -> CommissionRecord | None:
    """Record a commission with idempotency protection.

    Returns the CommissionRecord if created, None if already exists.
    """
    existing = (
        db.query(CommissionRecord)
        .filter(CommissionRecord.business_id == business_id)
        .first()
    )
    if existing:
        logger.info(
            "Commission already recorded: business_id=%s", business_id
        )
        return None

    record = CommissionRecord(
        user_id=user_id,
        amount=amount,
        type=commission_type,
        source_user_id=source_user_id,
        business_id=business_id,
    )
    db.add(record)
    db.flush()

    AuditService.log(
        action="commission_create",
        operator_type="system",
        target_type="commission_record",
        target_id=record.id,
        old_value=None,
        new_value={
            "user_id": user_id,
            "amount": str(amount),
            "type": commission_type,
            "source_user_id": source_user_id,
            "business_id": business_id,
        },
        business_id=business_id,
        db=db,
    )

    logger.info(
        "Commission recorded: user_id=%d amount=%.2f type=%s business_id=%s",
        user_id,
        amount,
        commission_type,
        business_id,
    )
    return record


class CommissionEngine:
    """Commission calculation and recording engine.

    Pipeline: calculate → record → log
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate(
        self, user_id: int, scene: str, context: dict | None = None
    ) -> dict:
        """Calculate commission amount for a given user and scene.

        Returns a dict with keys: user_id, amount, commission_type, business_id.
        This is a skeleton — full implementation in Epic 2.
        """
        raise NotImplementedError(
            f"Commission calculation not implemented for scene={scene}"
        )

    def record(
        self,
        user_id: int,
        amount: float,
        commission_type: str,
        source_user_id: int | None,
        business_id: str,
    ) -> CommissionRecord | None:
        """Record a commission with idempotency protection."""
        return record_commission(
            user_id=user_id,
            amount=amount,
            commission_type=commission_type,
            source_user_id=source_user_id,
            business_id=business_id,
            db=self.db,
        )

    def log_audit(
        self,
        action: str,
        target_type: str,
        target_id: int,
        old_value: dict | None,
        new_value: dict | None,
        business_id: str,
    ) -> None:
        """Write an audit log entry."""
        AuditService.log(
            action=action,
            operator_type="system",
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            business_id=business_id,
            db=self.db,
        )
