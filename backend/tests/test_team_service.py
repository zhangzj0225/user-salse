"""Tests for app.services.team_service — 团队树与上级链。"""

import pytest

from app.models.user import User
from app.services.team_service import TeamService


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


class TestGetTeamTree:
    def test_single_user_no_downline(self, db_session):
        """无下级用户 → total_count=0, children=[]"""
        user = _make_user(db_session, "solo@example.com")
        service = TeamService()
        result = service.get_team_tree(user.id, db_session)

        assert result["total_count"] == 0
        assert result["root"]["user_id"] == user.id
        assert result["root"]["direct_downline_count"] == 0
        assert result["root"]["children"] == []

    def test_direct_downline(self, db_session):
        """直接下级"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        c1 = _make_user(db_session, "c1@example.com", parent_id=agent.id)
        c2 = _make_user(db_session, "c2@example.com", parent_id=agent.id)

        service = TeamService()
        result = service.get_team_tree(agent.id, db_session)

        assert result["total_count"] == 2
        assert result["root"]["direct_downline_count"] == 2
        assert len(result["root"]["children"]) == 2

    def test_multi_level_tree(self, db_session):
        """多层团队树: A → B → C, A → D"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        dist = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "child@example.com", parent_id=dist.id)
        d = _make_user(db_session, "d@example.com", parent_id=agent.id)

        service = TeamService()
        result = service.get_team_tree(agent.id, db_session)

        assert result["total_count"] == 3
        assert result["root"]["direct_downline_count"] == 2

        # 找到 dist 节点
        dist_node = next(c for c in result["root"]["children"] if c["user_id"] == dist.id)
        assert dist_node["direct_downline_count"] == 1
        assert dist_node["children"][0]["user_id"] == child.id

    def test_nonexistent_user(self, db_session):
        service = TeamService()
        with pytest.raises(ValueError, match="不存在"):
            service.get_team_tree(9999, db_session)

    def test_node_fields(self, db_session):
        """验证节点包含所有必要字段"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=agent.id)

        service = TeamService()
        result = service.get_team_tree(agent.id, db_session)

        child_node = result["root"]["children"][0]
        assert "user_id" in child_node
        assert "email" in child_node
        assert "nickname" in child_node
        assert "role" in child_node
        assert "created_at" in child_node
        assert "direct_downline_count" in child_node
        assert "children" in child_node
        assert child_node["email"] == "child@example.com"
        assert child_node["role"] == "user"


class TestGetUpstreamChain:
    def test_no_parent(self, db_session):
        """无上级用户 → 空链"""
        user = _make_user(db_session, "root@example.com")
        service = TeamService()
        result = service.get_upstream_chain(user.id, db_session)

        assert result["chain"] == []

    def test_single_level(self, db_session):
        """单级上级"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=agent.id)

        service = TeamService()
        result = service.get_upstream_chain(child.id, db_session)

        assert len(result["chain"]) == 1
        assert result["chain"][0]["user_id"] == agent.id
        assert result["chain"][0]["level"] == 1
        assert result["chain"][0]["role"] == "agent"

    def test_multi_level(self, db_session):
        """多级上级: C → B → A"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        dist = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        child = _make_user(db_session, "child@example.com", parent_id=dist.id)

        service = TeamService()
        result = service.get_upstream_chain(child.id, db_session)

        assert len(result["chain"]) == 2
        assert result["chain"][0]["user_id"] == dist.id
        assert result["chain"][0]["level"] == 1
        assert result["chain"][1]["user_id"] == agent.id
        assert result["chain"][1]["level"] == 2

    def test_nonexistent_user(self, db_session):
        service = TeamService()
        with pytest.raises(ValueError, match="不存在"):
            service.get_upstream_chain(9999, db_session)

    def test_chain_node_fields(self, db_session):
        """验证链节点包含所有必要字段"""
        agent = _make_user(db_session, "agent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=agent.id)

        service = TeamService()
        result = service.get_upstream_chain(child.id, db_session)

        node = result["chain"][0]
        assert "user_id" in node
        assert "email" in node
        assert "nickname" in node
        assert "role" in node
        assert "level" in node
