"""Tests for Story 4.4 系统参数配置。"""

import pytest
from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.user import User
from app.services.system_config_service import reset_config_initialization


@pytest.fixture(autouse=True)
def _reset_config_init():
    """每个测试前重置初始化标志，确保 _ensure_defaults 在干净 DB 上运行。"""
    reset_config_initialization()
    yield
    reset_config_initialization()


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.commit()
    return admin


class TestSystemConfigAPI:
    def test_requires_admin_auth(self, client):
        resp = client.get("/api/v1/admin/configs")
        assert resp.status_code == 401

    def test_requires_admin_role(self, client, db_session):
        user = User(email="user@example.com", role="distributor", status="active")
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=user.id, role="distributor", token_type="user")
        resp = client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_list_configs_auto_init(self, client, db_session):
        """首次访问自动初始化默认配置。"""
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        configs = resp.json()["configs"]
        assert len(configs) >= 8
        keys = {c["config_key"] for c in configs}
        assert "payment_amount_888" in keys
        assert "quota_for_agent" in keys
        assert "min_withdrawal_amount" in keys

    def test_get_single_config(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        # First call to init
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/v1/admin/configs/quota_for_agent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["config_key"] == "quota_for_agent"
        assert data["config_value"] == "22"

    def test_get_nonexistent_config(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.get(
            "/api/v1/admin/configs/nonexistent_key",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_update_config(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        # Init
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.put(
            "/api/v1/admin/configs/min_withdrawal_amount",
            json={"config_value": "200"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["config_value"] == "200"

    def test_update_nonexistent_config(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.put(
            "/api/v1/admin/configs/nonexistent_key",
            json={"config_value": "100"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_config_change_log(self, client, db_session):
        """更新配置后查看变更日志。"""
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        # Init
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Update
        client.put(
            "/api/v1/admin/configs/quota_for_agent",
            json={"config_value": "30"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Check logs
        resp = client.get(
            "/api/v1/admin/config-change-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        logs = resp.json()["logs"]
        assert len(logs) >= 1
        latest = logs[0]
        assert latest["config_key"] == "quota_for_agent"
        assert latest["old_value"] == "22"
        assert latest["new_value"] == "30"
        assert latest["admin_id"] == admin.id

    def test_multiple_changes_logged(self, client, db_session):
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        # Init
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Multiple updates
        client.put(
            "/api/v1/admin/configs/quota_for_agent",
            json={"config_value": "30"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.put(
            "/api/v1/admin/configs/quota_for_agent",
            json={"config_value": "40"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/v1/admin/config-change-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        logs = resp.json()["logs"]
        assert len(logs) >= 2

    def test_update_config_invalid_int_value(self, client, db_session):
        """整数型配置传入非数字应报错。"""
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.put(
            "/api/v1/admin/configs/quota_for_agent",
            json={"config_value": "abc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_update_config_negative_value(self, client, db_session):
        """负数值应报错。"""
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.put(
            "/api/v1/admin/configs/quota_for_agent",
            json={"config_value": "-5"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_update_config_invalid_decimal_value(self, client, db_session):
        """小数型配置传入非数字应报错。"""
        admin = _make_admin(db_session)
        token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        client.get(
            "/api/v1/admin/configs",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.put(
            "/api/v1/admin/configs/followup_reward_amount",
            json={"config_value": "not_a_number"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
