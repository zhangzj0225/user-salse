"""Tests for Story 5.2 消息通知。"""

from decimal import Decimal

from app.core.security import create_access_token
from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.invite_code import InviteCode
from app.models.notification_log import NotificationLog
from app.models.recharge import Recharge
from app.models.ticket import Ticket
from app.models.user import User
from app.services.notification_service import NotificationService


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.commit()
    return admin


class TestNotificationService:
    """NotificationService 单元测试。"""

    def test_send_creates_log(self, db_session):
        _make_user(db_session, "u@example.com")
        db_session.flush()
        user = db_session.query(User).first()

        notif = NotificationService.send(
            user_id=user.id,
            event_type="test_event",
            content={"key": "value"},
            db=db_session,
        )
        db_session.commit()

        assert notif.id is not None
        assert notif.event_type == "test_event"
        assert notif.sent is False
        assert notif.content == {"key": "value"}

    def test_notify_subordinate_registered(self, db_session):
        parent = _make_user(db_session, "parent@example.com", "agent")
        db_session.flush()

        notif = NotificationService.notify_subordinate_registered(
            parent_id=parent.id,
            child_email="child@example.com",
            db=db_session,
        )
        db_session.commit()

        assert notif.event_type == "subordinate_registered"
        assert notif.user_id == parent.id
        assert notif.content["child_email"] == "child@example.com"

    def test_notify_commission_credited(self, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.flush()

        notif = NotificationService.notify_commission_credited(
            user_id=user.id,
            amount="500.00",
            commission_type="first_reward",
            db=db_session,
        )
        db_session.commit()

        assert notif.event_type == "commission_credited"
        assert notif.content["amount"] == "500.00"
        assert notif.content["type"] == "first_reward"

    def test_notify_ticket_status_changed(self, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.flush()

        notif = NotificationService.notify_ticket_status_changed(
            user_id=user.id,
            ticket_id=1,
            old_status="pending",
            new_status="paid",
            reason=None,
            db=db_session,
        )
        db_session.commit()

        assert notif.event_type == "ticket_status_changed"
        assert notif.content["new_status"] == "paid"

    def test_notify_recharge_approved(self, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.flush()

        notif = NotificationService.notify_recharge_approved(
            user_id=user.id,
            amount="888",
            new_role="member",
            db=db_session,
        )
        db_session.commit()

        assert notif.event_type == "recharge_approved"
        assert notif.content["new_role"] == "member"

    def test_list_user_notifications(self, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.flush()

        for i in range(5):
            NotificationService.send(user.id, "test", {"i": i}, db_session)
        db_session.commit()

        notifications, total = NotificationService.list_user_notifications(user.id, db_session)
        assert total == 5
        assert len(notifications) == 5

    def test_mark_as_read(self, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.flush()

        notif = NotificationService.send(user.id, "test", {}, db_session)
        db_session.commit()

        success = NotificationService.mark_as_read(notif.id, user.id, db_session)
        assert success is True

        updated = db_session.query(NotificationLog).filter(NotificationLog.id == notif.id).first()
        assert updated.sent is True

    def test_mark_as_read_wrong_user(self, db_session):
        """不能标记别人的通知。"""
        user1 = _make_user(db_session, "u1@example.com")
        user2 = _make_user(db_session, "u2@example.com")
        db_session.flush()

        notif = NotificationService.send(user1.id, "test", {}, db_session)
        db_session.commit()

        success = NotificationService.mark_as_read(notif.id, user2.id, db_session)
        assert success is False


class TestNotificationAPI:
    """通知 API 测试。"""

    def test_list_notifications(self, client, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.commit()

        NotificationService.send(user.id, "test_event", {"k": "v"}, db_session)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["notifications"][0]["event_type"] == "test_event"

    def test_list_notifications_requires_auth(self, client):
        resp = client.get("/api/v1/users/me/notifications")
        assert resp.status_code == 401

    def test_mark_notification_read(self, client, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.commit()

        notif = NotificationService.send(user.id, "test", {}, db_session)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            f"/api/v1/users/me/notifications/{notif.id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_mark_nonexistent_notification(self, client, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.post(
            "/api/v1/users/me/notifications/99999/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_pagination(self, client, db_session):
        user = _make_user(db_session, "u@example.com")
        db_session.commit()

        for i in range(10):
            NotificationService.send(user.id, "test", {"i": i}, db_session)
        db_session.commit()

        token = create_access_token(subject=user.id, role="user", token_type="user")
        resp = client.get(
            "/api/v1/users/me/notifications?limit=3&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["notifications"]) == 3
        assert data["total"] == 10


class TestNotificationTriggers:
    """验证通知在业务流程中自动触发。"""

    def test_recharge_approval_triggers_notification(self, client, db_session):
        """充值审核通过后用户收到通知。"""
        admin = _make_admin(db_session)
        user = _make_user(db_session, "u@example.com", "user")
        db_session.add(Recharge(user_id=user.id, amount=888, target_role="member", status="pending"))
        db_session.commit()
        recharge = db_session.query(Recharge).first()

        admin_token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/recharges/{recharge.id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

        # 验证通知已创建
        notifs = db_session.query(NotificationLog).filter(
            NotificationLog.user_id == user.id,
            NotificationLog.event_type == "recharge_approved",
        ).all()
        assert len(notifs) == 1
        assert notifs[0].content["new_role"] == "member"

    def test_ticket_approval_triggers_notification(self, client, db_session):
        """工单审核后用户收到通知。"""
        admin = _make_admin(db_session)
        user = _make_user(db_session, "u@example.com", "user")
        db_session.add(Ticket(
            user_id=user.id, amount=Decimal("100"),
            payment_method="alipay", status="pending",
        ))
        db_session.commit()
        ticket = db_session.query(Ticket).first()

        admin_token = create_access_token(subject=admin.id, role="super_admin", token_type="admin")
        resp = client.post(
            f"/api/v1/admin/tickets/{ticket.id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

        notifs = db_session.query(NotificationLog).filter(
            NotificationLog.user_id == user.id,
            NotificationLog.event_type == "ticket_status_changed",
        ).all()
        assert len(notifs) == 1
        assert notifs[0].content["new_status"] == "paid"
