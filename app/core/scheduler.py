"""
Background job sync — APScheduler.

Enabled by setting JOB_SYNC_QUERIES in .env (semicolon-separated search terms).
Every JOB_SYNC_INTERVAL_HOURS the scheduler ingests each query from all
sources and embeds whatever is new — the job pool stays fresh without anyone
calling /jobs/ingest by hand.

Opt-in by design: no env var, no scheduler, no surprise API usage.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import JOB_SYNC_QUERIES, JOB_SYNC_INTERVAL_HOURS, JOB_SYNC_COUNTRY
from app.core.database import SessionLocal
from app.services.job_ingestion import ingest_from_sources, embed_pending_jobs

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _sync_all_queries() -> None:
    db = SessionLocal()
    try:
        for query in JOB_SYNC_QUERIES:
            result = ingest_from_sources(db, query, country=JOB_SYNC_COUNTRY)
            logger.info(
                "Job sync '%s': %d ingested, %d deduplicated",
                query, result["total_ingested"], result["total_deduplicated"],
            )
        embedded = embed_pending_jobs(db)
        logger.info("Job sync: embedded %d new jobs", embedded)
    except Exception:
        # A failed cycle must never kill the scheduler; next run may succeed.
        logger.exception("Job sync cycle failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not JOB_SYNC_QUERIES:
        logger.info("Job sync disabled (JOB_SYNC_QUERIES not set)")
        return
    if _scheduler is not None:
        return  # already running (uvicorn --reload re-imports modules)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _sync_all_queries,
        trigger="interval",
        hours=JOB_SYNC_INTERVAL_HOURS,
        id="job_sync",
        max_instances=1,        # never overlap two sync cycles
        coalesce=True,          # missed runs collapse into one
        next_run_time=datetime.now() + timedelta(seconds=15),  # first sync right after boot
    )
    _scheduler.start()
    logger.info(
        "Job sync scheduled: %d queries every %dh (country=%s)",
        len(JOB_SYNC_QUERIES), JOB_SYNC_INTERVAL_HOURS, JOB_SYNC_COUNTRY,
    )
