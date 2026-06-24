"""Tests for payment API endpoints。"""

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.user import User


class TestCreatePaymentAPI:
    def test_create_success(self, client, db_session):
        resp = client.post("/api/v1/payments/create", json={
            "email": "api888@example.com",
            "amount": 888,
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["amount"] == "888.00"
        assert data["target_role"] == "member_license"
        assert data["status"] == "pending"

    def test_create_5000(self, client, db_session):
        resp = client.post("/api/v1/payments/create", json={
            "email": "api5000@example.com",
            "amount": 5000,
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["target_role"] == "distributor"

    def test_create_invalid_amount(self, client, db_session):
        resp = client.post("/api/v1/payments/create", json={
            "email": "api_invalid@example.com",
            "amount": 100,
        })
        # S5: 金额校验从 Pydantic validator 移至 service 层动态读取 SystemConfig
        assert resp.status_code == 400

    def test_create_missing_email(self, client, db_session):
        resp = client.post("/api/v1/payments/create", json={
            "amount": 888,
        })
        assert resp.status_code == 422


class TestListPaymentsAPI:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/payments")
        assert resp.status_code == 401

    def test_list_returns_own(self, client, db_session):
        user = User(email="list_own@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()

        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        # 888 支付不关联用户，列表应为空
        resp = client.get(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 0


class TestPaymentStatusAPI:
    def test_get_status_success(self, client, db_session):
        # 先创建用户并获取 token
        user = User(email="status@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=user.id, role="distributor", token_type="user")

        # 先创建支付
        create_resp = client.post("/api/v1/payments/create", json={
            "email": "status@example.com",
            "amount": 888,
        })
        payment_id = create_resp.json()["data"]["id"]

        resp = client.get(
            f"/api/v1/payments/{payment_id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "pending"

    def test_get_status_not_found(self, client, db_session):
        user = User(email="status_nf@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=user.id, role="distributor", token_type="user")

        resp = client.get(
            "/api/v1/payments/9999/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestAdminPaymentAPI:
    def _make_admin_token(self, db_session):
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.commit()
        return create_access_token(subject=admin.id, role="admin", token_type="admin")

    def _make_user_token(self, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        return create_access_token(subject=user.id, role="distributor", token_type="user")

    def test_admin_list_requires_admin_token(self, client, db_session):
        """user token → 403"""
        token = self._make_user_token(db_session)
        resp = client.get(
            "/api/v1/admin/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_list_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        # 创建支付
        client.post("/api/v1/payments/create", json={
            "email": "admin_list@example.com",
            "amount": 888,
        })

        resp = client.get(
            "/api/v1/admin/payments",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["total"] == 1

    def test_admin_list_filter_by_status(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        # 创建第一笔并 approve
        resp1 = client.post("/api/v1/payments/create", json={
            "email": "filter1@example.com",
            "amount": 888,
        })
        payment1_id = resp1.json()["data"]["id"]

        client.post(
            f"/api/v1/admin/payments/{payment1_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )

        # 创建第二笔 pending
        resp2 = client.post("/api/v1/payments/create", json={
            "email": "filter2@example.com",
            "amount": 888,
        })
        payment2_id = resp2.json()["data"]["id"]

        # 筛选 pending — 只返回第二个
        resp_pending = client.get(
            "/api/v1/admin/payments?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_pending.status_code == 200
        pending_data = resp_pending.json()
        assert pending_data["total"] == 1
        assert pending_data["data"][0]["id"] == payment2_id

        # 筛选 paid — 只返回第一个
        resp_paid = client.get(
            "/api/v1/admin/payments?status=paid",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_paid.status_code == 200
        paid_data = resp_paid.json()
        assert paid_data["total"] == 1
        assert paid_data["data"][0]["id"] == payment1_id

    def test_admin_list_invalid_status(self, client, db_session):
        """无效状态参数返回 400"""
        admin_token = self._make_admin_token(db_session)
        resp = client.get(
            "/api/v1/admin/payments?status=foobar",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_admin_approve_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        create_resp = client.post("/api/v1/payments/create", json={
            "email": "approve@example.com",
            "amount": 888,
        })
        payment_id = create_resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/admin/payments/{payment_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "paid"

    def test_admin_approve_already_processed(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        create_resp = client.post("/api/v1/payments/create", json={
            "email": "dup_approve@example.com",
            "amount": 888,
        })
        payment_id = create_resp.json()["data"]["id"]

        client.post(
            f"/api/v1/admin/payments/{payment_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )

        resp = client.post(
            f"/api/v1/admin/payments/{payment_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert resp.status_code == 400

    def test_admin_reject_success(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        create_resp = client.post("/api/v1/payments/create", json={
            "email": "reject@example.com",
            "amount": 888,
        })
        payment_id = create_resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/admin/payments/{payment_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reject_reason": "未收到款项"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "failed"
        assert data["reject_reason"] is not None

    def test_admin_reject_without_reason(self, client, db_session):
        admin_token = self._make_admin_token(db_session)

        create_resp = client.post("/api/v1/payments/create", json={
            "email": "reject_no_reason@example.com",
            "amount": 888,
        })
        payment_id = create_resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/admin/payments/{payment_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert resp.status_code == 422

    def test_admin_endpoints_require_admin_token(self, client, db_session):
        """user token 调用 admin 端点 → 403"""
        token = self._make_user_token(db_session)

        resp = client.get(
            "/api/v1/admin/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

        resp = client.post(
            "/api/v1/admin/payments/1/approve",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

        resp = client.post(
            "/api/v1/admin/payments/1/reject",
            headers={"Authorization": f"Bearer {token}"},
            json={"reject_reason": "test"},
        )
        assert resp.status_code == 403
