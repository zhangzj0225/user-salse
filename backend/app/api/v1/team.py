"""团队树与上级链 API 端点。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.team_service import TeamService, get_team_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me", tags=["team"])


@router.get("/team")
def get_team_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """查看我的团队（下级树）。

    返回当前用户的完整下级树，支持逐层展开。
    """
    try:
        result = service.get_team_tree(current_user.id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/upstream")
def get_upstream_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """查看我的上级链条。

    从直接上级开始，一直追溯到根节点。
    根节点显示为链条的最后一项（无上级则返回空列表）。
    """
    try:
        result = service.get_upstream_chain(current_user.id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
