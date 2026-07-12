"""Source registry — one line per connector. Currently Adzuna only.

The plugin architecture stays: to add a source later, create a connector
implementing JobSource (see base.py) and register it here.
"""

from app.services.job_sources.base import JobSource
from app.services.job_sources.adzuna_source import AdzunaSource

_SOURCES: dict[str, JobSource] = {
    s.name: s for s in (AdzunaSource(),)
}


def available_sources() -> list[str]:
    return sorted(_SOURCES.keys())


def resolve_sources(names: str | None) -> list[JobSource]:
    """
    Resolves a comma-separated source list to connector instances.
    None or "all" -> every registered source.
    Raises ValueError for unknown names so typos fail loudly, not silently.
    """
    if not names or names.strip().lower() == "all":
        return list(_SOURCES.values())

    resolved = []
    for name in (n.strip().lower() for n in names.split(",")):
        if name not in _SOURCES:
            raise ValueError(f"Unknown job source '{name}'. Available: {available_sources()}")
        resolved.append(_SOURCES[name])
    return resolved
