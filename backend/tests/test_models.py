"""Tests for new and refactored database models."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.user import User
from app.models.email_verification_code import EmailVerificationCode
from app.models.invite_code import InviteCode
from app.models.recharge import Recharge
from app.models.sale import Sale
from app.models.license import License
from app.models.commission_config import CommissionConfig
from app.models.commission_record import CommissionRecord
from app.models.ticket import Ticket
from app.models.config_change_log import ConfigChangeLog
from app.models.notification_log import NotificationLog
from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog


class TestUserModel:
    def test_create_user_with_email(self, db_session):
        user = User(email="user@example.com", role="user", status="active")
        db_session.add(user)
        db_session.commit()
        assert user.id is not None
        assert user.email == "user@example.com"
        assert user.role == "user"
        assert user.status == "active"

    def test_email_is_unique(self, db_session):
        user1 = User(email="dup@example.com", role="user", status="active")
        db_session.add(user1)
        db_session.commit()

        user2 = User(email="dup@example.com", role="user", status="active")
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_role_supports_member(self, db_session):
        user = User(email="member@example.com", role="member", status="active")
        db_session.add(user)
        db_session.commit()
        assert user.role == "member"

    def test_role_supports_agent(self, db_session):
        user = User(email="agent@example.com", role="agent", status="active", account_quota=22)
        db_session.add(user)
        db_session.commit()
        assert user.role == "agent"
        assert user.account_quota == 22

    def test_default_status_is_active(self, db_session):
        user = User(email="default@example.com")
        db_session.add(user)
        db_session.commit()
        assert user.status == "active"

    def test_parent_child_relationship(self, db_session):
        parent = User(email="parent@example.com", role="agent", status="active")
        db_session.add(parent)
        db_session.flush()

        child = User(email="child@example.com", role="user", status="active", parent_id=parent.id)
        db_session.add(child)
        db_session.commit()

        assert child.parent_id == parent.id


class TestEmailVerificationCodeModel:
    def test_create_code(self, db_session):
        record = EmailVerificationCode(
            email="test@example.com",
            code="123456",
            scene="register",
            expires_at=datetime.now(timezone.utc),
        )
        db_session.add(record)
        db_session.commit()
        assert record.id is not None
        assert record.verified is False


class TestInviteCodeModel:
    def test_create_invite_code_without_target_role(self, db_session):
        user = User(email="gen@example.com", role="agent", status="active")
        db_session.add(user)
        db_session.flush()

        code = InviteCode(code="ABC123.SIG", generator_id=user.id)
        db_session.add(code)
        db_session.commit()
        assert code.id is not None
        assert code.used_by is None
        assert code.used_at is None


class TestRechargeModel:
    def test_create_recharge(self, db_session):
        user = User(email="recharge@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        recharge = Recharge(user_id=user.id, amount=888.00, target_role="member")
        db_session.add(recharge)
        db_session.commit()
        assert recharge.id is not None
        assert recharge.status == "pending"
        assert recharge.target_role == "member"


class TestSaleModel:
    def test_create_sale_with_customer_email(self, db_session):
        seller = User(email="seller@example.com", role="agent", status="active")
        db_session.add(seller)
        db_session.flush()

        sale = Sale(seller_id=seller.id, customer_email="customer@example.com")
        db_session.add(sale)
        db_session.commit()
        assert sale.id is not None
        assert sale.customer_email == "customer@example.com"


class TestLicenseModel:
    def test_create_license(self, db_session):
        user = User(email="lic@example.com", role="member", status="active")
        db_session.add(user)
        db_session.flush()

        lic = License(
            code="LIC-ABC123",
            user_id=user.id,
            email="lic@example.com",
            source="recharge",
        )
        db_session.add(lic)
        db_session.commit()
        assert lic.id is not None
        assert lic.status == "unused"
        assert lic.source == "recharge"


class TestCommissionConfigModel:
    def test_create_config(self, db_session):
        config = CommissionConfig(
            role="agent",
            scene="recharge_888",
            reward_type="fixed",
            reward_value=488.40,
        )
        db_session.add(config)
        db_session.commit()
        assert config.id is not None
        assert config.role == "agent"
        assert config.scene == "recharge_888"
        assert config.reward_type == "fixed"
        assert config.reward_value == Decimal("488.4000")

    def test_role_supports_member(self, db_session):
        config = CommissionConfig(
            role="member",
            scene="recharge_888",
            reward_type="fixed",
            reward_value=177.60,
        )
        db_session.add(config)
        db_session.commit()
        assert config.role == "member"

    def test_role_scene_unique(self, db_session):
        c1 = CommissionConfig(role="agent", scene="recharge_888", reward_type="fixed", reward_value=488.40)
        db_session.add(c1)
        db_session.commit()

        c2 = CommissionConfig(role="agent", scene="recharge_888", reward_type="fixed", reward_value=999.99)
        db_session.add(c2)
        with pytest.raises(Exception):
            db_session.commit()


class TestCommissionRecordModel:
    def test_create_record_with_followup_reward(self, db_session):
        user = User(email="rec@example.com", role="agent", status="active")
        db_session.add(user)
        db_session.flush()

        record = CommissionRecord(
            user_id=user.id,
            amount=133.20,
            type="followup_reward",
            business_id="recharge_1_followup_1",
        )
        db_session.add(record)
        db_session.commit()
        assert record.id is not None
        assert record.type == "followup_reward"

    def test_business_id_is_unique(self, db_session):
        user = User(email="uniq@example.com", role="agent", status="active")
        db_session.add(user)
        db_session.flush()

        rec1 = CommissionRecord(
            user_id=user.id, amount=100, type="first_reward", business_id="uniq_001"
        )
        db_session.add(rec1)
        db_session.commit()

        rec2 = CommissionRecord(
            user_id=user.id, amount=200, type="first_reward", business_id="uniq_001"
        )
        db_session.add(rec2)
        with pytest.raises(Exception):
            db_session.commit()


class TestTicketModel:
    def test_create_ticket(self, db_session):
        user = User(email="tick@example.com", role="agent", status="active")
        db_session.add(user)
        db_session.flush()

        ticket = Ticket(
            user_id=user.id, amount=500.00, payment_method="bank_card:1234"
        )
        db_session.add(ticket)
        db_session.commit()
        assert ticket.id is not None
        assert ticket.status == "pending"


class TestConfigChangeLogModel:
    def test_create_config_change_log(self, db_session):
        admin = AdminUser(username="admin", password_hash="hash")
        db_session.add(admin)
        db_session.flush()

        log = ConfigChangeLog(
            admin_id=admin.id,
            config_key="recharge_888",
            old_value="488.40",
            new_value="500.00",
        )
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.config_key == "recharge_888"
        assert log.old_value == "488.40"
        assert log.new_value == "500.00"


class TestNotificationLogModel:
    def test_create_notification_log(self, db_session):
        user = User(email="notif@example.com", role="user", status="active")
        db_session.add(user)
        db_session.flush()

        log = NotificationLog(
            user_id=user.id,
            event_type="commission_earned",
            content={"amount": "488.40", "source": "recharge"},
        )
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.event_type == "commission_earned"
        assert log.sent is False
        assert log.content["amount"] == "488.40"


class TestInviteCodeUniqueness:
    def test_code_is_unique(self, db_session):
        user = User(email="inv-uniq@example.com", role="agent", status="active")
        db_session.add(user)
        db_session.flush()

        code1 = InviteCode(code="UNIQUE_CODE.SIG", generator_id=user.id)
        db_session.add(code1)
        db_session.commit()

        code2 = InviteCode(code="UNIQUE_CODE.SIG", generator_id=user.id)
        db_session.add(code2)
        with pytest.raises(Exception):
            db_session.commit()


class TestLicenseUniqueness:
    def test_code_is_unique(self, db_session):
        user = User(email="lic-uniq@example.com", role="member", status="active")
        db_session.add(user)
        db_session.flush()

        lic1 = License(code="LIC-UNIQUE", user_id=user.id, email="lic-uniq@example.com", source="recharge")
        db_session.add(lic1)
        db_session.commit()

        lic2 = License(code="LIC-UNIQUE", user_id=user.id, email="lic-uniq@example.com", source="recharge")
        db_session.add(lic2)
        with pytest.raises(Exception):
            db_session.commit()
