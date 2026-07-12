"""Adzuna connector — wraps the existing client/normalizer behind the JobSource contract."""

from app.services.job_sources.base import JobSource, JobSourceError
from app.services.job_sources.adzuna_client import fetch_jobs
from app.services.job_sources.adzuna_normalizer import normalize_adzuna_job


class AdzunaSource(JobSource):
    name = "adzuna"
    requires_api_key = True

    def fetch(
        self,
        query: str,
        *,
        country: str = "gb",
        location: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        try:
            raw_jobs = fetch_jobs(query=query, country=country, location=location, results=limit)
        except Exception as e:
            raise JobSourceError(f"Adzuna fetch failed: {e}") from e
        return [normalize_adzuna_job(raw) for raw in raw_jobs]
