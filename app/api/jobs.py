from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.job_ingestion import ingest_from_sources, embed_pending_jobs
from app.services.job_sources.registry import available_sources

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/sources")
def list_sources():
    """Lists the job source connectors available for ingestion."""
    return {"sources": available_sources()}


@router.post("/ingest")
def ingest_jobs(
    query: str = Query(..., description="Search term, e.g. 'backend engineer'"),
    sources: str = Query("all", description="Comma-separated sources, or 'all'"),
    country: str = Query("gb"),
    location: str | None = Query(None),
    results: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    """
    Fetches jobs from one or more sources, deduplicates across sources
    (same title+company stored once), and upserts by source job ID.
    """
    try:
        return ingest_from_sources(
            db,
            query,
            sources=sources,
            country=country,
            location=location,
            limit=results,
        )
    except ValueError as e:  # unknown source name
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/embed-pending")
def embed_pending(db: Session = Depends(get_db)):
    return {"embedded_count": embed_pending_jobs(db)}
