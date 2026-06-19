"""Tests for commission config management and idempotency (Story 3.9)。

验证：
- get_config(role, scene) 查询 commission_configs 表
- 配置不存在时返回 None
- business_id UNIQUE 约束保证幂等
- 并发场景下 IntegrityError 捕获后降级返回 None
- record_commission 幂等行为
"""

import pytest
from decimal import Decimal

from app.models.admin_user import AdminUser
from app.models.commission_record import CommissionRecord
from app.models.user import User
from app.services.commission_service import CommissionEngine, record_commission
from app.services.recharge_service import RechargeService


def _make_admin(db):
    admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
    db.add(admin)
    db.flush()
    return admin


def _make_user(db, email, role="user", parent_id=None):
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    return u


class TestGetConfig:
    """AC1-2: get_config 查询 + 配置不存在返回 None。"""

    def test_get_config_existing(self, db_session, seed_commission_configs):
        """查询存在的配置"""
        engine = CommissionEngine(db_session)
        config = engine.get_config("agent", "recharge_888")
        assert config is not None
        assert config.reward_value == Decimal("488.40")
        assert config.reward_type == "fixed"

    def test_get_config_nonexistent_returns_none(self, db_session, seed_commission_configs):
        """配置不存在时返回 None"""
        engine = CommissionEngine(db_session)
        config = engine.get_config("user", "recharge_5000")
        assert config is None

    def test_get_config_all_seed_roles(self, db_session, seed_commission_configs):
        """验证 4 角色种子数据可查询"""
        engine = CommissionEngine(db_session)
        for role in ("user", "member", "distributor", "agent"):
            config = engine.get_config(role, "recharge_888")
            assert config is not None, f"role={role} config missing"


class TestBusinessIdUniqueness:
    """AC3: business_id UNIQUE 约束。"""

    def test_duplicate_business_id_rejected(self, db_session, seed_commission_configs):
        """直接插入重复 business_id 抛 IntegrityError"""
        from sqlalchemy.exc import IntegrityError

        record1 = CommissionRecord(
            user_id=1,
            amount=Decimal("100.00"),
            type="first_reward",
            source_user_id=2,
            business_id="recharge_999",
        )
        db_session.add(record1)
        db_session.flush()

        record2 = CommissionRecord(
            user_id=1,
            amount=Decimal("200.00"),
            type="first_reward",
            source_user_id=2,
            business_id="recharge_999",
        )
        db_session.add(record2)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestRecordCommissionIdempotency:
    """AC3-4: record_commission 幂等 — IntegrityError 捕获后返回 None。"""

    def test_record_commission_idempotent(self, db_session, seed_commission_configs):
        """相同 business_id 第二次调用返回 None（不抛异常）"""
        # 第一次记录
        result1 = record_commission(
            user_id=1,
            amount=Decimal("100.00"),
            commission_type="first_reward",
            source_user_id=2,
            business_id="recharge_test_1",
            db=db_session,
        )
        assert result1 is not None
        assert result1.business_id == "recharge_test_1"

        # 第二次相同 business_id → 返回 None
        result2 = record_commission(
            user_id=1,
            amount=Decimal("100.00"),
            commission_type="first_reward",
            source_user_id=2,
            business_id="recharge_test_1",
            db=db_session,
        )
        assert result2 is None

        # DB 中只有一条记录
        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == "recharge_test_1"
        ).all()
        assert len(records) == 1


class TestConcurrentIdempotency:
    """AC4: 并发场景下不产生重复记录。"""

    def test_no_duplicate_on_concurrent_flush(self, db_session, seed_commission_configs):
        """模拟并发插入 — IntegrityError 被捕获，不产生重复"""
        results = []
        for i in range(3):
            r = record_commission(
                user_id=1,
                amount=Decimal("100.00"),
                commission_type="first_reward",
                source_user_id=2,
                business_id="recharge_concurrent_1",
                db=db_session,
            )
            results.append(r)

        # 第一次成功，后两次返回 None
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is None

        # DB 只有一条
        count = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == "recharge_concurrent_1"
        ).count()
        assert count == 1


class TestEndToEndIdempotency:
    """端到端幂等：approve_recharge 重复调用不产生重复佣金。"""

    def test_reapprove_no_duplicate_commission(self, db_session, seed_commission_configs):
        """重复批准充值 → 状态机拦截 + 无重复佣金"""
        admin = _make_admin(db_session)
        parent = _make_user(db_session, "parent@example.com", "agent")
        child = _make_user(db_session, "child@example.com", parent_id=parent.id)

        service = RechargeService()
        recharge = service.create_recharge(child.id, 888, db_session)
        service.approve_recharge(recharge.id, admin.id, db_session)

        # 尝试再次批准 → 状态机拦截
        with pytest.raises(ValueError, match="充值已处理"):
            service.approve_recharge(recharge.id, admin.id, db_session)

        # 佣金记录仍只有一条
        records = db_session.query(CommissionRecord).filter(
            CommissionRecord.business_id == f"recharge_{recharge.id}"
        ).all()
        assert len(records) == 1
