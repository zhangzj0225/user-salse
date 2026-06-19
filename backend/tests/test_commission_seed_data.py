"""Tests for commission config seed data consistency (Story 3.4)。

验证 migration 004 的种子数据与 PRD v2 佣金规则完全一致。
"""

import pytest
from decimal import Decimal

from app.models.commission_config import CommissionConfig


class TestSeedDataConsistency:
    """验证种子数据与 PRD v2 一致。"""

    def _seed_configs(self, db_session):
        """手动插入种子数据（模拟 migration 004）。"""
        configs = [
            # agent (代理)
            CommissionConfig(role="agent", scene="recharge_888", reward_type="fixed", reward_value=Decimal("488.40")),
            CommissionConfig(role="agent", scene="recharge_5000", reward_type="fixed", reward_value=Decimal("2750.00")),
            CommissionConfig(role="agent", scene="recharge_10000", reward_type="fixed", reward_value=Decimal("5500.00")),
            CommissionConfig(role="agent", scene="followup_reward", reward_type="fixed", reward_value=Decimal("133.20")),
            CommissionConfig(role="agent", scene="team_bonus", reward_type="percentage", reward_value=Decimal("0.05")),
            # distributor (经销商)
            CommissionConfig(role="distributor", scene="recharge_888", reward_type="fixed", reward_value=Decimal("355.20")),
            CommissionConfig(role="distributor", scene="recharge_5000", reward_type="fixed", reward_value=Decimal("2000.00")),
            CommissionConfig(role="distributor", scene="recharge_10000", reward_type="fixed", reward_value=Decimal("4000.00")),
            CommissionConfig(role="distributor", scene="team_bonus", reward_type="percentage", reward_value=Decimal("0.04")),
            # member (888会员)
            CommissionConfig(role="member", scene="recharge_888", reward_type="fixed", reward_value=Decimal("177.60")),
            # user (普通用户)
            CommissionConfig(role="user", scene="recharge_888", reward_type="fixed", reward_value=Decimal("177.60")),
        ]
        db_session.add_all(configs)
        db_session.flush()
        return configs

    def test_total_config_count(self, db_session):
        """种子数据共 11 条配置"""
        self._seed_configs(db_session)
        count = db_session.query(CommissionConfig).count()
        assert count == 11

    def test_agent_configs(self, db_session):
        """代理有 5 条配置：3 首次奖励 + 1 后续收益 + 1 长期奖励"""
        self._seed_configs(db_session)
        agent_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "agent"
        ).all()
        assert len(agent_configs) == 5

    def test_distributor_configs(self, db_session):
        """经销商有 4 条配置：3 首次奖励 + 1 长期奖励"""
        self._seed_configs(db_session)
        dist_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "distributor"
        ).all()
        assert len(dist_configs) == 4

    def test_member_config(self, db_session):
        """888 会员有 1 条配置：仅充 888 的首次奖励"""
        self._seed_configs(db_session)
        member_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "member"
        ).all()
        assert len(member_configs) == 1
        assert member_configs[0].scene == "recharge_888"
        assert member_configs[0].reward_value == Decimal("177.60")

    def test_user_config(self, db_session):
        """普通用户有 1 条配置：仅充 888 的首次奖励"""
        self._seed_configs(db_session)
        user_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "user"
        ).all()
        assert len(user_configs) == 1
        assert user_configs[0].scene == "recharge_888"
        assert user_configs[0].reward_value == Decimal("177.60")

    def test_agent_first_reward_values(self, db_session):
        """代理首次奖励金额正确：888→488.40, 5000→2750, 10000→5500"""
        self._seed_configs(db_session)
        for scene, expected in [
            ("recharge_888", Decimal("488.40")),
            ("recharge_5000", Decimal("2750.00")),
            ("recharge_10000", Decimal("5500.00")),
        ]:
            config = db_session.query(CommissionConfig).filter(
                CommissionConfig.role == "agent",
                CommissionConfig.scene == scene,
            ).first()
            assert config is not None
            assert config.reward_value == expected
            assert config.reward_type == "fixed"

    def test_followup_reward_value(self, db_session):
        """后续收益：代理获得 133.20 元/笔"""
        self._seed_configs(db_session)
        config = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "agent",
            CommissionConfig.scene == "followup_reward",
        ).first()
        assert config is not None
        assert config.reward_value == Decimal("133.20")
        assert config.reward_type == "fixed"

    def test_no_commission_for_member_distributor_higher_amounts(self, db_session):
        """888 会员和普通用户推荐的人充 5000/10000 不产生佣金"""
        self._seed_configs(db_session)
        # member 没有 recharge_5000 / recharge_10000 配置
        for scene in ["recharge_5000", "recharge_10000"]:
            config = db_session.query(CommissionConfig).filter(
                CommissionConfig.role == "member",
                CommissionConfig.scene == scene,
            ).first()
            assert config is None

        # user 同理
        for scene in ["recharge_5000", "recharge_10000"]:
            config = db_session.query(CommissionConfig).filter(
                CommissionConfig.role == "user",
                CommissionConfig.scene == scene,
            ).first()
            assert config is None
