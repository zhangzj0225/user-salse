"""Tests for app.services.recharge_service — 充值申请、审核服务。"""

import pytest

from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog
from app.models.recharge import Recharge
from app.models.user import User
from app.services.recharge_service import RechargeService


class TestCreateRecharge:
    def test_create_recharge_888(self, db_session):
        user = User(email="u888@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)

        assert recharge.id is not None
        assert int(recharge.amount) == 888
        assert recharge.target_role == "member"
        assert recharge.status == "pending"

    def test_create_recharge_5000(self, db_session):
        user = User(email="u5000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 5000, db_session)

        assert recharge.target_role == "distributor"
        assert recharge.status == "pending"

    def test_create_recharge_10000(self, db_session):
        user = User(email="u10000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        recharge = service.create_recharge(user.id, 10000, db_session)

        assert recharge.target_role == "agent"
        assert recharge.status == "pending"

    def test_create_recharge_invalid_amount(self, db_session):
        user = User(email="invalid@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        with pytest.raises(ValueError, match="充值金额"):
            service.create_recharge(user.id, 100, db_session)


class TestApproveRecharge:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_approve_changes_role_888(self, db_session):
        user = User(email="a888@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.role == "member"

    def test_approve_changes_role_5000(self, db_session):
        user = User(email="a5000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 5000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.role == "distributor"

    def test_approve_changes_role_10000(self, db_session):
        user = User(email="a10000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 10000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.role == "agent"

    def test_approve_adds_quota_5000(self, db_session):
        user = User(email="q5000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 5000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.account_quota == 11

    def test_approve_adds_quota_10000(self, db_session):
        user = User(email="q10000@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 10000, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.account_quota == 22

    def test_approve_no_quota_888(self, db_session):
        user = User(email="q888@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        db_session.refresh(user)
        assert user.account_quota == 0

    def test_approve_independent_recharges(self, db_session):
        """888 会员再充 5000 → role=distributor, quota=0+11=11"""
        user = User(email="indep@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        # 第一次充 888
        r1 = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(r1.id, admin.id, db_session)
        db_session.refresh(user)
        assert user.role == "member"
        assert user.account_quota == 0

        # 第二次充 5000
        r2 = service.create_recharge(user.id, 5000, db_session)
        service.approve_recharge(r2.id, admin.id, db_session)
        db_session.refresh(user)
        assert user.role == "distributor"
        assert user.account_quota == 11  # 0 + 11

    def test_approve_writes_audit(self, db_session):
        user = User(email="audit@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "recharge_approve",
            AuditLog.target_id == recharge.id,
        ).all()
        assert len(logs) == 1

    def test_approve_already_processed(self, db_session):
        user = User(email="processed@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        with pytest.raises(ValueError, match="充值已处理"):
            service.approve_recharge(recharge.id, admin.id, db_session)

    def test_approve_nonexistent(self, db_session):
        admin = self._make_admin(db_session)
        service = RechargeService()
        with pytest.raises(ValueError, match="不存在"):
            service.approve_recharge(9999, admin.id, db_session)


class TestRejectRecharge:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_reject_success(self, db_session):
        user = User(email="reject@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.reject_recharge(recharge.id, admin.id, "未收到款项", db_session)

        db_session.refresh(recharge)
        db_session.refresh(user)
        assert recharge.status == "rejected"
        assert recharge.reject_reason == "未收到款项"
        assert user.role == "user"  # 角色不变
        assert user.account_quota == 0  # 额度不变

    def test_reject_writes_audit(self, db_session):
        user = User(email="reject_audit@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.reject_recharge(recharge.id, admin.id, "测试拒绝", db_session)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "recharge_reject",
            AuditLog.target_id == recharge.id,
        ).all()
        assert len(logs) == 1

    def test_reject_already_processed(self, db_session):
        user = User(email="reject_done@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        recharge = service.create_recharge(user.id, 888, db_session)
        service.reject_recharge(recharge.id, admin.id, "拒绝", db_session)

        with pytest.raises(ValueError, match="充值已处理"):
            service.reject_recharge(recharge.id, admin.id, "再拒绝", db_session)


class TestListRecharges:
    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_list_user_recharges(self, db_session):
        user = User(email="list@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        # BH-5: 同用户不能同时有多笔 pending，故 approve 第一笔后再建第二笔
        r1 = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(r1.id, admin.id, db_session)
        service.create_recharge(user.id, 5000, db_session)

        recharges = service.list_user_recharges(user.id, db_session)
        assert len(recharges) == 2

    def test_list_user_recharges_only_own(self, db_session):
        user1 = User(email="u1@example.com", role="user", status="active")
        user2 = User(email="u2@example.com", role="user", status="active")
        db_session.add_all([user1, user2])
        db_session.flush()

        service = RechargeService()
        service.create_recharge(user1.id, 888, db_session)
        service.create_recharge(user2.id, 5000, db_session)

        recharges = service.list_user_recharges(user1.id, db_session)
        assert len(recharges) == 1
        assert recharges[0].user_id == user1.id

    def test_list_recharges_with_status_filter(self, db_session):
        user = User(email="filter@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        r1 = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(r1.id, admin.id, db_session)
        # BH-5: 第一笔 approve 后才能建第二笔 pending
        r2 = service.create_recharge(user.id, 5000, db_session)

        pending, pending_total = service.list_recharges(db_session, status="pending")
        assert len(pending) == 1
        assert pending[0].id == r2.id

        all_recharges, all_total = service.list_recharges(db_session)
        assert len(all_recharges) == 2


class TestRechargeRoleAndDedup:
    """BH-3 角色降级防护 + BH-5 pending 去重。"""

    def _make_admin(self, db_session) -> AdminUser:
        admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_role_not_downgraded_on_lower_recharge(self, db_session):
        """BH-3: agent 充 888 不得降级为 member，应保持 agent。"""
        user = User(email="agent@example.com", role="agent", status="active", account_quota=22)
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        r = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(r.id, admin.id, db_session)
        db_session.refresh(user)

        # 代理身份保留，未降级为 member
        assert user.role == "agent"
        # 额度仍累加（888 不带额度，但原有 22 保留）
        assert user.account_quota == 22

    def test_role_upgrades_to_higher(self, db_session):
        """BH-3: member 充 10000 升级为 agent（取最高档）。"""
        user = User(email="member@example.com", role="member", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        r = service.create_recharge(user.id, 10000, db_session)
        service.approve_recharge(r.id, admin.id, db_session)
        db_session.refresh(user)
        assert user.role == "agent"
        assert user.account_quota == 22

    def test_cannot_create_second_pending_recharge(self, db_session):
        """BH-5: 同用户已有 pending 充值时，新建被拒。"""
        user = User(email="dedup@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        service = RechargeService()
        service.create_recharge(user.id, 888, db_session)
        with pytest.raises(ValueError, match="待审核"):
            service.create_recharge(user.id, 5000, db_session)

    def test_can_create_after_first_approved(self, db_session):
        """BH-5: 第一笔 approve 后可建第二笔。"""
        user = User(email="seq@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()
        admin = self._make_admin(db_session)

        service = RechargeService()
        r1 = service.create_recharge(user.id, 888, db_session)
        service.approve_recharge(r1.id, admin.id, db_session)
        # approve 后无 pending，可建第二笔
        r2 = service.create_recharge(user.id, 5000, db_session)
        assert r2.status == "pending"
