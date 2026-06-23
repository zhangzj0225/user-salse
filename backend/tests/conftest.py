import os

# 测试环境默认 dev：SEC-1 默认 ENV=production（fail-closed），测试需显式降级，
# 否则 TestClient startup 会因默认密钥抛 RuntimeError。必须在 import app.* 之前设置。
os.environ["ENV"] = "dev"
os.environ["AUTH_MODE"] = "mock"

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# CRITICAL: Import models FIRST so they register with Base.metadata
import app.models  # noqa: F401 — imports all models via __init__.py
from app.core.database import Base
from app.models.commission_config import CommissionConfig


@pytest.fixture(scope="session")
def test_engine():
    """Create a shared in-memory SQLite engine for all tests."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a fresh DB session for each test, with transaction rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """FastAPI TestClient with SQLite DB and overridden get_db."""
    # Monkeypatch the engine creation to use SQLite
    monkeypatch.setattr(
        "app.core.database.get_engine",
        lambda: test_engine,
    )

    from app.main import app
    from app.core.database import get_db
    from fastapi.testclient import TestClient

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_commission_configs(db_session):
    """插入 11 条佣金配置种子数据（与 migration 004 一致）。

    ⚠️ 此 fixture 验证的是"手动插入的数据"而非 migration 文件本身。
    如果 migration 004 被修改但此处未同步，测试可能无法捕获差异。
    修改 migration 时请同步更新此 fixture。
    """
    configs = [
        # agent (代理) — 5 条
        CommissionConfig(role="agent", scene="first_reward_888", reward_type="fixed", reward_value=Decimal("488.40")),
        CommissionConfig(role="agent", scene="first_reward_5000", reward_type="fixed", reward_value=Decimal("2750.00")),
        CommissionConfig(role="agent", scene="first_reward_10000", reward_type="fixed", reward_value=Decimal("5500.00")),
        CommissionConfig(role="agent", scene="followup_reward", reward_type="fixed", reward_value=Decimal("133.20")),
        CommissionConfig(role="agent", scene="team_bonus", reward_type="percentage", reward_value=Decimal("0.05")),
        # distributor (经销商) — 4 条
        CommissionConfig(role="distributor", scene="first_reward_888", reward_type="fixed", reward_value=Decimal("355.20")),
        CommissionConfig(role="distributor", scene="first_reward_5000", reward_type="fixed", reward_value=Decimal("2000.00")),
        CommissionConfig(role="distributor", scene="first_reward_10000", reward_type="fixed", reward_value=Decimal("4000.00")),
        CommissionConfig(role="distributor", scene="team_bonus", reward_type="percentage", reward_value=Decimal("0.04")),
    ]
    db_session.add_all(configs)
    db_session.flush()
    return configs
