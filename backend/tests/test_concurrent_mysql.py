"""D8: MySQL 并发测试 — 验证行锁真实生效。

这些测试需要真实 MySQL（非 SQLite），因为 SQLite 的 with_for_update() 是 no-op。

运行方式:
  1. 启动 MySQL 容器:
     docker compose -f docker-compose.test.yml up -d
  2. 运行测试:
     cd backend
     TEST_DB_URL="mysql+pymysql://test:test@127.0.0.1:3307/user_salse_test" \
       python -m pytest tests/test_concurrent_mysql.py -v -s
  3. 关闭容器:
     docker compose -f docker-compose.test.yml down

默认（无 TEST_DB_URL 环境变量时）全部跳过，不影响 SQLite 测试套件。
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 检查是否配置了 MySQL 测试数据库
MYSQL_TEST_URL = os.environ.get("TEST_DB_URL", "")
HAS_MYSQL = bool(MYSQL_TEST_URL)

pytestmark = pytest.mark.skipif(
    not HAS_MYSQL,
    reason="需要 TEST_DB_URL 环境变量指向 MySQL 测试数据库。"
    "运行: docker compose -f docker-compose.test.yml up -d && "
    'TEST_DB_URL="mysql+pymysql://test:test@127.0.0.1:3307/user_salse_test" pytest tests/test_concurrent_mysql.py -v',
)


@pytest.fixture(scope="module")
def mysql_engine():
    """创建 MySQL 测试引擎，建表，测试后销毁。"""
    import app.models  # noqa: F401
    from app.core.database import Base

    eng = create_engine(MYSQL_TEST_URL, echo=False)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def mysql_session_factory(mysql_engine):
    """返回 session 工厂，每个测试自行创建/关闭 session。"""
    return sessionmaker(autocommit=False, autoflush=False, bind=mysql_engine)


def _seed_user(mysql_session_factory):
    """创建测试用户和佣金记录。"""
    from app.models.user import User
    from app.models.commission_record import CommissionRecord

    Session = mysql_session_factory
    db = Session()
    try:
        user = User(email="concurrent@example.com", role="distributor", status="active")
        db.add(user)
        db.flush()
        # 给用户 1000 元佣金余额
        record = CommissionRecord(
            user_id=user.id,
            amount=Decimal("1000.00"),
            type="first_reward",
            business_id="seed_concurrent_1",
        )
        db.add(record)
        db.commit()
        return user.id
    finally:
        db.close()


class TestConcurrentWithdrawal:
    """并发提现测试 — 验证 with_for_update() 行锁防止超额提现。"""

    def test_concurrent_withdrawal_no_overspend(self, mysql_session_factory):
        """两个线程同时提现 800 元（余额 1000），应只成功一笔。"""
        from app.services.withdrawal_service import WithdrawalService

        user_id = _seed_user(mysql_session_factory)

        results = []
        barrier = threading.Barrier(2)  # 确保两线程同时开始

        def withdraw():
            Session = mysql_session_factory
            db = Session()
            try:
                barrier.wait()  # 同步启动
                service = WithdrawalService()
                result = service.create_ticket(user_id, "800.00", "支付宝:test", db)
                results.append(("success", result))
            except Exception as e:
                results.append(("error", str(e)))
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(withdraw) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        # 应该只有 1 个成功，1 个失败（余额不足）
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}: {results}"

    def test_concurrent_payment_approve_no_double_role(self, mysql_session_factory):
        """两个管理员同时批准同一支付 — 应只成功一次。"""
        from app.models.admin_user import AdminUser
        from app.models.payment import Payment
        from app.services.payment_service import PaymentService

        Session = mysql_session_factory
        db = Session()
        try:
            admin = AdminUser(username="admin", password_hash="hash", role="super_admin")
            db.add(admin)
            db.flush()
            payment = Payment(
                email="approve@example.com", amount=888, target_role="member_license",
                status="pending",
            )
            db.add(payment)
            db.commit()
            payment_id = payment.id
            admin_id = admin.id
        finally:
            db.close()

        results = []
        barrier = threading.Barrier(2)

        def approve():
            Session = mysql_session_factory
            db = Session()
            try:
                barrier.wait()
                service = PaymentService()
                result = service.approve_payment(payment_id, admin_id, db)
                results.append(("success", result.id))
            except Exception as e:
                results.append(("error", str(e)))
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        # 应该只有 1 个成功（状态机 + 行锁）
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}: {results}"
        assert "已处理" in errors[0][1] or "Lock" in errors[0][1]


class TestConcurrentLicenseActivate:
    """并发 License 激活测试。"""

    def test_concurrent_activate_no_double(self, mysql_session_factory):
        """两个请求同时激活同一 License — 应只成功一次。"""
        from app.models.user import User
        from app.models.license import License
        from app.services.license_service import _generate_license_code, LicenseService

        Session = mysql_session_factory
        db = Session()
        try:
            user = User(email="license@example.com", role="distributor", status="active")
            db.add(user)
            db.flush()
            code = _generate_license_code(user.id, nonce="abcd1234")
            lic = License(
                code=code, user_id=user.id,
                source="payment", source_id=1, status="unused",
            )
            db.add(lic)
            db.commit()
        finally:
            db.close()

        results = []
        barrier = threading.Barrier(2)

        def activate():
            Session = mysql_session_factory
            db = Session()
            try:
                barrier.wait()
                service = LicenseService()
                result = service.activate_license(code, "license@example.com", None, db)
                results.append(result)
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(activate) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}: {results}"
        assert "已激活" in failures[0]["message"] or "Lock" in failures[0]["message"]
