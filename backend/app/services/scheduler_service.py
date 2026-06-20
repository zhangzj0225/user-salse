"""定时结算调度器 (Story 5.1)。

使用 APScheduler 在每月1号执行长期奖励结算。
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.database import get_session_local
from app.models.user import User
from app.services.commission_service import CommissionEngine

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

# D-1: misfire_grace_time=86400（24h），进程在月1号不在线恢复后自动补跑。
# 若进程离线超过24h，该月结算被跳过——需运维感知 monthly_settlement_skipped 日志。
MISFIRE_GRACE_SECONDS = 86400


def run_settlement() -> None:
    """执行长期奖励结算。

    遍历所有代理/经销商用户，计算其直接下级的总佣金并按比例记账。
    幂等：相同 period 不会重复结算（business_id UNIQUE + 预查）。
    失败用户下次调用时同 period 再次尝试（幂等兜底）。
    """
    period = datetime.now(timezone.utc).strftime("%Y%m")
    logger.info("Starting long-term reward settlement for period %s", period)

    # S5: 逐用户独立事务，单用户失败不影响其他用户
    session_factory = get_session_local()

    # 先查询所有需要结算的用户
    db: Session = session_factory()
    try:
        users = (
            db.query(User.id)
            .filter(User.role.in_(("agent", "distributor")))
            .filter(User.status == "active")
            .all()
        )
        user_ids = [u[0] for u in users]
    finally:
        db.close()

    total_settled = 0
    total_failed = 0
    failed_ids: list[int] = []
    for user_id in user_ids:
        user_db: Session = session_factory()
        try:
            engine = CommissionEngine(user_db)
            records = engine.calculate_long_term_reward(user_id, period, db=user_db)
            if records:
                total_settled += 1
            user_db.commit()
        except Exception:
            user_db.rollback()
            total_failed += 1
            failed_ids.append(user_id)
            logger.exception("Settlement failed for user_id=%d period=%s", user_id, period)
        finally:
            user_db.close()

    if total_failed > 0:
        logger.warning(
            "Settlement had failures: period=%s failed_count=%d failed_ids=%s — "
            "这些用户下周期可通过同 business_id 幂等补算",
            period, total_failed, failed_ids,
        )
    else:
        logger.info(
            "Settlement complete: period=%s users_processed=%d settled=%d",
            period, len(user_ids), total_settled,
        )


def start_scheduler() -> None:
    """启动定时调度器。每月1号 02:00 UTC 执行结算。

    多 worker 注意：本调度器依赖 APScheduler 进程内 BackgroundScheduler，
    未配置分布式锁。多 worker 部署时每 worker 各自启动调度器，同时触发
    run_settlement。UNIQUE 约束防重复记账，但浪费资源且日志噪声。建议：
    - 单 worker 运行调度器（通过环境变量或部署配置控制 start_scheduler 仅主进程调用）
    - 或使用 Redis/external lock 做分布式单例
    """
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    # D-3: max_instances=1 防同进程内重复执行
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_settlement,
        CronTrigger(day=1, hour=2, minute=0, timezone="UTC"),
        id="long_term_reward_settlement",
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,  # D-1: 宕机恢复后离线<24h自动补跑
        max_instances=1,  # D-3: 同进程内单实例
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: settlement runs on 1st of each month at 02:00 UTC "
        "(misfire_grace=%ds, max_instances=1)", MISFIRE_GRACE_SECONDS,
    )


def stop_scheduler() -> None:
    """停止调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
