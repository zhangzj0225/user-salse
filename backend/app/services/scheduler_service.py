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


def run_settlement() -> None:
    """执行长期奖励结算。

    遍历所有代理/经销商用户，计算其直接下级的总佣金并按比例记账。
    幂等：相同周期不会重复结算。
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
            logger.exception("Settlement failed for user_id=%d period=%s", user_id, period)
        finally:
            user_db.close()

    logger.info(
        "Settlement complete: period=%s users_processed=%d settled=%d",
        period, len(user_ids), total_settled,
    )


def start_scheduler() -> None:
    """启动定时调度器。每月1号 02:00 UTC 执行结算。"""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_settlement,
        CronTrigger(day=1, hour=2, minute=0, timezone="UTC"),
        id="long_term_reward_settlement",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: settlement runs on 1st of each month at 02:00 UTC")


def stop_scheduler() -> None:
    """停止调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
