"""Tests for commission config seed data consistency (Story 3.4)。

验证种子数据与 PRD v2 佣金规则完全一致。
⚠️ 注意：此测试验证的是 conftest.py 中 seed_commission_configs fixture 的数据，
而非 migration 004 文件本身。修改 migration 时请同步更新 fixture。
"""

from decimal import Decimal

from app.models.commission_config import CommissionConfig


class TestSeedDataConsistency:
    """验证种子数据与 PRD v2 一致。"""

    def test_total_config_count(self, db_session, seed_commission_configs):
        """种子数据共 9 条配置"""
        count = db_session.query(CommissionConfig).count()
        assert count == 9

    def test_agent_configs(self, db_session, seed_commission_configs):
        """代理有 5 条配置：3 首次奖励 + 1 后续收益 + 1 长期奖励"""
        agent_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "agent"
        ).all()
        assert len(agent_configs) == 5

    def test_distributor_configs(self, db_session, seed_commission_configs):
        """经销商有 4 条配置：3 首次奖励 + 1 长期奖励"""
        dist_configs = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "distributor"
        ).all()
        assert len(dist_configs) == 4

    def test_agent_first_reward_values(self, db_session, seed_commission_configs):
        """代理首次奖励金额正确：888→488.40, 5000→2750, 10000→5500"""
        for scene, expected in [
            ("first_reward_888", Decimal("488.40")),
            ("first_reward_5000", Decimal("2750.00")),
            ("first_reward_10000", Decimal("5500.00")),
        ]:
            config = db_session.query(CommissionConfig).filter(
                CommissionConfig.role == "agent",
                CommissionConfig.scene == scene,
            ).first()
            assert config is not None
            assert config.reward_value == expected
            assert config.reward_type == "fixed"

    def test_distributor_first_reward_values(self, db_session, seed_commission_configs):
        """经销商首次奖励金额正确：888→355.20, 5000→2000, 10000→4000"""
        for scene, expected in [
            ("first_reward_888", Decimal("355.20")),
            ("first_reward_5000", Decimal("2000.00")),
            ("first_reward_10000", Decimal("4000.00")),
        ]:
            config = db_session.query(CommissionConfig).filter(
                CommissionConfig.role == "distributor",
                CommissionConfig.scene == scene,
            ).first()
            assert config is not None
            assert config.reward_value == expected

    def test_followup_reward_value(self, db_session, seed_commission_configs):
        """后续收益：代理获得 133.20 元/笔"""
        config = db_session.query(CommissionConfig).filter(
            CommissionConfig.role == "agent",
            CommissionConfig.scene == "followup_reward",
        ).first()
        assert config is not None
        assert config.reward_value == Decimal("133.20")
        assert config.reward_type == "fixed"
