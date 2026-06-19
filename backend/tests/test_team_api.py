"""Tests for team API endpoints。"""

from app.core.security import create_access_token
from app.models.user import User


class TestTeamAPI:
    def test_team_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/team")
        assert resp.status_code == 401

    def test_team_empty(self, client, db_session):
        user = User(email="solo@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/team",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert data["root"]["user_id"] == user.id
        assert data["root"]["children"] == []

    def test_team_with_downline(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active", nickname="Agent王")
        db_session.add(agent)
        db_session.commit()

        c1 = User(email="c1@example.com", role="user", status="active", parent_id=agent.id, nickname="小C1")
        c2 = User(email="c2@example.com", role="user", status="active", parent_id=agent.id, nickname="小C2")
        db_session.add_all([c1, c2])
        db_session.commit()

        token = create_access_token(subject=agent.id, role="agent", token_type="user")
        resp = client.get(
            "/api/v1/users/me/team",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 2
        assert len(data["root"]["children"]) == 2

        # S5: 验证子节点字段
        child = data["root"]["children"][0]
        assert child["nickname"] == "小C1"
        assert child["role"] == "user"
        assert "created_at" in child
        assert child["direct_downline_count"] == 0
        assert child["children"] == []
        # M2: 不应返回 email
        assert "email" not in child


class TestUpstreamAPI:
    def test_upstream_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/upstream")
        assert resp.status_code == 401

    def test_upstream_no_parent(self, client, db_session):
        user = User(email="root@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/upstream",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["chain"] == []

    def test_upstream_with_parent(self, client, db_session):
        agent = User(email="agent@example.com", role="agent", status="active", nickname="Agent王")
        db_session.add(agent)
        db_session.commit()

        child = User(email="child@example.com", role="user", status="active", parent_id=agent.id)
        db_session.add(child)
        db_session.commit()

        token = create_access_token(subject=child.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/upstream",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        chain = resp.json()["chain"]
        assert len(chain) == 1
        assert chain[0]["user_id"] == agent.id
        assert chain[0]["level"] == 1
        assert chain[0]["nickname"] == "Agent王"
        # M2: 不应返回 email
        assert "email" not in chain[0]
