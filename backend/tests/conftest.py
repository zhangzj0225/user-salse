import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# CRITICAL: Import models FIRST so they register with Base.metadata
import app.models.user  # noqa: F401
import app.models.sms_record  # noqa: F401
import app.models.admin_user  # noqa: F401
import app.models.commission_record  # noqa: F401
import app.models.audit_log  # noqa: F401
from app.core.database import Base


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
