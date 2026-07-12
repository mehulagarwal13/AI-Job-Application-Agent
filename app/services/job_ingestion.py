"""
Ingestion service — the one place jobs enter the system.

Used by both the /jobs/ingest endpoint and the background scheduler, so the
pipeline (fetch -> validate -> dedup -> upsert) exists exactly once.

Cross-source deduplication: different boards list the same role. Every job
gets a dedup_key = sha1(normalized_title | normalized_company); if a job with
that key already exists from ANY source, the incoming copy is skipped.
"""

import hashlib
import logging
import re

from sqlalchemy.orm import Session

from app.services.job_sources.base import JobSource, JobSourceError
from app.services.job_sources.registry import resolve_sources
from app.services import job_repository
from app.services.job_text_builder import build_job_summary_text
from app.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)


def compute_dedup_key(title: str, company: str | None) -> str:
    """Stable key for 'same role at same company' regardless of source/formatting."""
    normalized = re.sub(r"[^a-z0-9]+", " ", f"{title} {company or ''}".lower()).strip()
    return hashlib.sha1(normalized.encode()).hexdigest()


def ingest_from_sources(
    db: Session,
    query: str,
    *,
    sources: str | None = None,
    country: str = "gb",
    location: str | None = None,
    limit: int = 20,
) -> dict:
    """
    Fetches from the requested sources and upserts. One failing source never
    aborts the run — its error is reported in the result instead.
    """
    connectors: list[JobSource] = resolve_sources(sources)
    per_source: dict[str, dict] = {}
    total_ingested = 0
    total_deduped = 0

    for connector in connectors:
        stats = {"fetched": 0, "ingested": 0, "deduplicated": 0, "error": None}
        try:
            jobs = connector.fetch(query, country=country, location=location, limit=limit)
            stats["fetched"] = len(jobs)

            for job_dict in jobs:
                if not job_dict["title"] or not job_dict["description"]:
                    continue  # skip garbage/incomplete listings

                job_dict["dedup_key"] = compute_dedup_key(
                    job_dict["title"], job_dict["company"]
                )

                # Cross-source dedup: same role+company already known -> skip.
                duplicate = job_repository.get_by_dedup_key(db, job_dict["dedup_key"])
                if duplicate and duplicate.job_id != job_dict["job_id"]:
                    stats["deduplicated"] += 1
                    total_deduped += 1
                    continue

                job_repository.upsert_job(db, job_dict)
                stats["ingested"] += 1
                total_ingested += 1

        except (JobSourceError, ValueError) as e:
            logger.warning("Source '%s' failed: %s", connector.name, e)
            stats["error"] = str(e)

        per_source[connector.name] = stats

    return {
        "query": query,
        "total_ingested": total_ingested,
        "total_deduplicated": total_deduped,
        "sources": per_source,
    }


def embed_pending_jobs(db: Session) -> int:
    """Embeds every job without a vector. Returns the count embedded."""
    pending = job_repository.get_unembedded_jobs(db)
    for job in pending:
        job.embedding_vector = generate_embedding(build_job_summary_text(job))
    db.commit()
    return len(pending)
