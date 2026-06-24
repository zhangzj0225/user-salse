"""团队树与上级链服务。"""

import logging

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

# 防止恶意深度递归
MAX_TEAM_DEPTH = 100


class TeamService:
    """团队树查询服务。"""

    def get_team_tree(self, user_id: int, db: Session) -> dict:
        """获取用户下级团队树。

        单次递归遍历构建树并统计总人数，保证两者一致。
        返回: {
            "total_count": int,
            "root": {
                "user_id": int,
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

        total_count, root = self._build_tree_recursive(user, db, depth=0, visited={user.id})

        return {
            "total_count": total_count,
            "root": root,
        }

    def _build_tree_recursive(
        self, user: User, db: Session, depth: int, visited: set
    ) -> tuple[int, dict]:
        """递归构建团队树，返回 (子树总数, 节点)。

        depth >= MAX_TEAM_DEPTH 时停止展开子节点，但仍计入总数。
        """
        children = (
            db.query(User)
            .filter(User.parent_id == user.id)
            .order_by(User.created_at.asc())
            .all()
        )

        child_nodes = []
        subtree_count = 0

        if depth < MAX_TEAM_DEPTH:
            for child in children:
                if child.id in visited:
                    logger.warning("检测到团队树循环: user_id=%d", child.id)
                    continue
                visited.add(child.id)
                subtree_count += 1
                child_count, child_node = self._build_tree_recursive(
                    child, db, depth + 1, visited
                )
                subtree_count += child_count
                child_nodes.append(child_node)
        else:
            # 超过最大深度，仍计入直接子节点数但不展开
            subtree_count += len(children)

        node = self._make_node(user, len(children))
        node["children"] = child_nodes

        return subtree_count, node

    def _make_node(self, user: User, direct_downline_count: int) -> dict:
        """创建树节点。PRD v2 FR-9: 展示每个下级的邮箱、角色、注册时间、下级数。"""
        return {
            "user_id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role,
            "created_at": user.created_at,
            "direct_downline_count": direct_downline_count,
            "children": [],
        }

    def get_upstream_chain(self, user_id: int, db: Session) -> dict:
        """获取用户上级链。

        从直接上级开始，一直追溯到根节点。
        返回: {"chain": [{"user_id", "nickname", "role", "level"}, ...]}
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
