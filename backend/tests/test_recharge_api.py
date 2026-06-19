"""Tests for recharge API endpoints。"""

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.user import User


class TestCreateRechargeAPI:
    def test_create_requires_auth(self, client):
        resp = client.post("/api/v1/recharges", json={"amount": 888})
        assert resp.status_code == 401

    def test_create_success(self, client, db_session):
        user = User(email="api888@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 888},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["amount"] == "888.00"
        assert data["target_role"] == "member"
        assert data["status"] == "pending"

    def test_create_invalid_amount(self, client, db_session):
        user = User(email="api_invalid@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 100},
        )
        # S1: schema 层 validator 拦截 → 422
        assert resp.status_code == 422


class TestListRechargesAPI:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/recharges")
        assert resp.status_code == 401

    def test_list_returns_own(self, client, db_session):
        user = User(email="list_own@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 888},
        )
        client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 5000},
        )

        resp = client.get(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2


class TestAdminRechargeAPI:
    def _make_admin_token(self, db_session):
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.commit()
        return create_access_token(subject=admin.id, role="admin", token_type="admin")

    def _make_user_token(self, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        return create_access_token(subject=user.id, role="user", token_type="user")

    def test_admin_list_requires_admin_token(self, client, db_session):
        """user token → 403"""
        token = self._make_user_token(db_session)
        resp = client.get(
            "/api/v1/admin/recharges",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_list_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建充值
        client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )

        resp = client.get(
            "/api/v1/admin/recharges",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["total"] == 1

    def test_admin_list_filter_by_status(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建充值
        resp1 = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )
        resp2 = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 5000},
        )
        recharge1_id = resp1.json()["data"]["id"]
        recharge2_id = resp2.json()["data"]["id"]

        # 批准第一个充值
        client.post(
            f"/api/v1/admin/recharges/{recharge1_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # 筛选 pending — 只返回第二个
        resp_pending = client.get(
            "/api/v1/admin/recharges?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_pending.status_code == 200
        pending_data = resp_pending.json()
        assert pending_data["total"] == 1
        assert pending_data["data"][0]["id"] == recharge2_id

        # 筛选 approved — 只返回第一个
        resp_approved = client.get(
            "/api/v1/admin/recharges?status=approved",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_approved.status_code == 200
        approved_data = resp_approved.json()
        assert approved_data["total"] == 1
        assert approved_data["data"][0]["id"] == recharge1_id

    def test_admin_list_invalid_status(self, client, db_session):
        """S2: 无效状态参数返回 400"""
        admin_token = self._make_admin_token(db_session)
        resp = client.get(
            "/api/v1/admin/recharges?status=foobar",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_admin_approve_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建充值
        create_resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )
        recharge_id = create_resp.json()["data"]["id"]

        # 批准
        resp = client.post(
            f"/api/v1/admin/recharges/{recharge_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "approved"

    def test_admin_approve_already_processed(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建并批准
        create_resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )
        recharge_id = create_resp.json()["data"]["id"]

        client.post(
            f"/api/v1/admin/recharges/{recharge_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # 重复批准
        resp = client.post(
            f"/api/v1/admin/recharges/{recharge_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_admin_reject_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建充值
        create_resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )
        recharge_id = create_resp.json()["data"]["id"]

        # 拒绝
        resp = client.post(
            f"/api/v1/admin/recharges/{recharge_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reject_reason": "未收到款项"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "rejected"
        assert data["reject_reason"] == "未收到款项"

    def test_admin_reject_without_reason(self, client, db_session):
        admin_token = self._make_admin_token(db_session)
        user_token = self._make_user_token(db_session)

        # 创建充值
        create_resp = client.post(
            "/api/v1/recharges",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"amount": 888},
        )
        recharge_id = create_resp.json()["data"]["id"]

        # 缺 reject_reason → 422
        resp = client.post(
            f"/api/v1/admin/recharges/{recharge_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert resp.status_code == 422

    def test_admin_endpoints_require_admin_token(self, client, db_session):
        """user token 调用 admin 端点 → 403"""
        token = self._make_user_token(db_session)

        # list
        resp = client.get(
            "/api/v1/admin/recharges",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

        # approve
        resp = client.post(
            "/api/v1/admin/recharges/1/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

        # reject
        resp = client.post(
            "/api/v1/admin/recharges/1/reject",
            headers={"Authorization": f"Bearer {token}"},
            json={"reject_reason": "test"},
        )
        assert resp.status_code == 403
