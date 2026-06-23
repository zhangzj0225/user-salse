"""End-to-end integration tests for payment → commission flow (Story 3.4)。

通过 PaymentService.approve_payment → CommissionEngine.process_payment
验证完整佣金记账流程。
"""

import pytest
from decimal import Decimal

from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.referral_code import ReferralCode
from app.models.user import User
from app.services.payment_service import PaymentService


def _make_admin(db_session):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db_session.add(admin)
    db_session.flush()
    return admin


def _make_user(db, email, role="distributor", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


def _make_referral_code(db, user_id):
    from app.core.security import generate_invite_code
    code = generate_invite_code(user_id)
    rc = ReferralCode(code=code, user_id=user_id, key_version=1)
    db.add(rc)
    db.flush()
    return rc


class TestFirstRewardBooking:
    """AC1-3: 首次奖励记账。"""

    def test_agent_parent_payment_888(self, db_session, seed_commission_configs):
        """代理上级，下级充 888 → 首次奖励 488.40"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        rc = _make_referral_code(db_session, parent.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=888,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert records[0].user_id == parent.id
        assert Decimal(records[0].amount) == Decimal("488.40")

    def test_agent_parent_payment_5000(self, db_session, seed_commission_configs):
        """代理上级，下级充 5000 → 首次奖励 2750.00"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        rc = _make_referral_code(db_session, parent.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=5000,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("2750.00")

    def test_agent_parent_payment_10000(self, db_session, seed_commission_configs):
        """代理上级，下级充 10000 → 首次奖励 5500.00"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        rc = _make_referral_code(db_session, parent.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=10000,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
            CommissionRecord.type == "first_reward",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("5500.00")

    def test_distributor_parent_payment_888(self, db_session, seed_commission_configs):
        """经销商上级，下级充 888 → 首次奖励 355.20"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "distributor")
        rc = _make_referral_code(db_session, parent.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=888,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
        ).all()
        assert len(records) == 1
        assert Decimal(records[0].amount) == Decimal("355.20")


class TestNoCommissionScenarios:
    """AC4: 无推荐码支付不产生佣金。"""

    def test_no_referral_code_no_commission(self, db_session, seed_commission_configs):
        """无推荐码支付 → 无佣金"""
        admin = _make_admin(db_session)

        service = PaymentService()
        payment = service.create_payment(
            email="noparent@example.com", amount=888,
            referral_code=None, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
        ).all()
        assert len(records) == 0


class TestIdempotency:
    """AC5: 同一笔支付不会重复记账（幂等）。"""

    def test_no_duplicate_commission_on_reapprove(self, db_session, seed_commission_configs):
        """重复批准同一支付不会产生重复佣金（状态机拦截）"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        rc = _make_referral_code(db_session, parent.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=888,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        with pytest.raises(ValueError, match="已处理"):
            service.approve_payment(payment.id, admin.id, db_session)

        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"payment_{payment.id}",
        ).all()
        assert len(records) == 1


class TestFollowupReward:
    """AC6: 后续收益（代理→经销商的下级充 888）。"""

    def test_followup_reward_agent_gets_133_20(self, db_session, seed_commission_configs):
        """C 充 888, B 是经销商, A 是代理 → A 获首次奖励 + 后续收益 133.20"""
        admin = _make_admin(db_session)

        agent = _make_user(db_session, "agent@example.com", "agent")
        distributor = _make_user(db_session, "dist@example.com", "distributor", parent_id=agent.id)
        rc = _make_referral_code(db_session, distributor.id)

        service = PaymentService()
        payment = service.create_payment(
            email="child@example.com", amount=888,
            referral_code=rc.code, redirect_url=None, db=db_session,
        )
        service.approve_payment(payment.id, admin.id, db_session)

        # 应有 2 条佣金记录：首次奖励（经销商获得 355.20）+ 后续收益（代理获得 133.20）
        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id.like(f"payment_{payment.id}%"),
        ).all()
        assert len(records) == 2

        first_reward = [r for r in records if r.type == "first_reward"]
        followup = [r for r in records if r.type == "followup_reward"]
        assert len(first_reward) == 1
        assert len(followup) == 1

        # 首次奖励给经销商
        assert first_reward[0].user_id == distributor.id
        assert Decimal(first_reward[0].amount) == Decimal("355.20")

        # 后续收益给代理
        assert followup[0].user_id == agent.id
        assert Decimal(followup[0].amount) == Decimal("133.20")
