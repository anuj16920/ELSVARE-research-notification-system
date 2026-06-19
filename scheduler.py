"""
scheduler.py - APScheduler wrapper that runs the monitoring job every 30 minutes
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

INTERVAL_MINUTES = 30


def build_scheduler(job_func, blocking: bool = True):
    """
    Build and return an APScheduler instance.

    Parameters
    ----------
    job_func   : callable – the monitoring job to run on each tick
    blocking   : bool     – True  → BlockingScheduler  (main.py production use)
                            False → BackgroundScheduler (testing / embedding)
    """
    SchedulerClass = BlockingScheduler if blocking else BackgroundScheduler
    scheduler = SchedulerClass(timezone="UTC")

    scheduler.add_job(
        func=job_func,
        trigger=IntervalTrigger(minutes=INTERVAL_MINUTES),
        id="paper_monitor",
        name="Elsevier paper monitor",
        replace_existing=True,
        max_instances=1,          # Prevent overlap if a run takes long
        misfire_grace_time=300,   # 5-minute grace window
    )

    logger.info(
        "Scheduler configured: job 'paper_monitor' every %d minutes", INTERVAL_MINUTES
    )
    return scheduler
