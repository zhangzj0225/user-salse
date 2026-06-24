import json
import logging

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def log(
        action: str,
        operator_type: str,
        target_type: str,
        target_id: int | None,
        old_value: dict | None,
        new_value: dict | None,
        business_id: str | None,
        db: Session,
        operator_id: int | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            operator_type=operator_type,
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            business_id=business_id,
            operator_id=operator_id,
        )
        db.add(entry)
        db.flush()
        logger.info(
            "Audit log: action=%s target=%s:%s business_id=%s",
            action,
            target_type,
            target_id,
            business_id,
        )
        return entry
