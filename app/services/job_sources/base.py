"""
Connector contract for job sources.

Every job board / aggregator implements JobSource and returns jobs in the
one internal normalized shape below. Adding a new source (LinkedIn, Jooble,
JSearch, Naukri...) = one connector file + one registry line. Nothing else
in the application changes.

Normalized job dict shape (keys must all be present):
{
    "job_id":             str   — globally unique, prefixed with source name,
    "title":              str,
    "company":            str | None,
    "location":           str | None,
    "description":        str,
    "salary_min":         str | None,
    "salary_max":         str | None,
    "remote":             str | None    — "yes" / "no" / None (unknown),
    "min_years_required": str | None,
    "apply_url":          str | None,
    "source":             str,
}
"""

from abc import ABC, abstractmethod


class JobSourceError(Exception):
    """Raised by connectors on fetch failure — one source failing must never break ingestion."""


class JobSource(ABC):
    name: str = "base"
    requires_api_key: bool = False

    @abstractmethod
    def fetch(
        self,
        query: str,
        *,
        country: str = "gb",
        location: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Fetches and returns normalized job dicts. Raises JobSourceError on failure."""
        raise NotImplementedError
