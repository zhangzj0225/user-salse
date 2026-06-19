"""团队树与上级链服务。"""

import logging

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

# 防止恶意深度递归
MAX_TEAM_DEPTH = 20


class TeamService:
    """团队树查询服务。"""

    def get_team_tree(self, user_id: int, db: Session) -> dict:
        """获取用户下级团队树。

        返回: {
            "total_count": int,
            "root": {
                "user_id": int,
                "email": str,
                "nickname": str | None,
                "role": str,
                "created_at": datetime,
                "direct_downline_count": int,
                "children": [...]
            }
        }
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        root = self._build_team_node(user, db, depth=0)
        total = self._count_total_downline(user.id, db)

        return {
            "total_count": total,
            "root": root,
        }

    def _build_team_node(self, user: User, db: Session, depth: int) -> dict:
        """递归构建团队树节点。"""
        children = (
            db.query(User)
            .filter(User.parent_id == user.id)
            .order_by(User.created_at.asc())
            .all()
        )

        child_nodes = []
        if depth < MAX_TEAM_DEPTH:
            for child in children:
                child_nodes.append(
                    self._build_team_node(child, db, depth + 1)
                )

        return {
            "user_id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role,
            "created_at": user.created_at,
            "direct_downline_count": len(children),
            "children": child_nodes,
        }

    def _count_total_downline(self, user_id: int, db: Session) -> int:
        """统计所有下级总数（递归 BFS）。"""
        total = 0
        queue = [user_id]
        visited = {user_id}

        while queue:
            current_id = queue.pop(0)
            children = (
                db.query(User)
                .filter(User.parent_id == current_id)
                .all()
            )
            for child in children:
                if child.id not in visited:
                    visited.add(child.id)
                    total += 1
                    queue.append(child.id)

        return total

    def get_upstream_chain(self, user_id: int, db: Session) -> dict:
        """获取用户上级链。

        从直接上级开始，一直追溯到根节点。
        返回: {"chain": [{"user_id", "email", "nickname", "role", "level"}, ...]}
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        chain = []
        current = user
        level = 0
        visited = {user.id}

        while current.parent_id:
            level += 1
            parent = db.query(User).filter(User.id == current.parent_id).first()
            if not parent:
                break
            if parent.id in visited:
                logger.warning("检测到上级链循环: user_id=%d", user_id)
                break
            visited.add(parent.id)

            chain.append({
                "user_id": parent.id,
                "email": parent.email,
                "nickname": parent.nickname,
                "role": parent.role,
                "level": level,
            })

            if level >= MAX_TEAM_DEPTH:
                logger.warning("上级链超过最大深度 %d: user_id=%d", MAX_TEAM_DEPTH, user_id)
                break

            current = parent

        return {"chain": chain}


def get_team_service() -> TeamService:
    return TeamService()
