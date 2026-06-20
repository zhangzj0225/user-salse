"""通知 API 端点 (Story 5.2)。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/users/me/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看我的通知列表。"""
    notifications, total = NotificationService.list_user_notifications(
        current_user.id, db, limit=limit, offset=offset
    )
    return {"notifications": notifications, "total": total}


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记通知为已读。"""
    success = NotificationService.mark_as_read(notification_id, current_user.id, db)
    if not success:
        return {"success": False, "message": "通知不存在"}
    db.commit()
    return {"success": True}
