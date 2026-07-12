import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db, SessionLocal
from app.models.db_models import JobRecord, MatchResult, User, VALID_MATCH_STATUSES
from app.models.match_response import MatchesResponse, JobMatchResponse
from app.models.parsed_resume import ParsedResume
from app.models.resume import ResumeUploadResponse
from app.services import resume_repository
from app.services.embedding_service import generate_embedding
from app.services.file_storage import save_resume_file, compute_file_hash
from app.services.match_repository import (
    save_match_results,
    get_matches_for_resume,
    get_match_by_id,
    update_match_status,
)
from app.services.matching.ranker import rank_jobs
from app.services.matching.retrieval import get_shortlist
from app.services.normalizer import normalize_resume
from app.services.resume_parser import parse_resume_text, ParsingError
from app.services.resume_text_builder import build_resume_summary_text
from app.services.text_extraction import extract_text, ExtractionError
from app.ai.llm import LLMRouterError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _get_owned_resume(db: Session, resume_id: str, user: User):
    """Fetches a resume iff it belongs to the current user; 404 otherwise.
    404 (not 403) so users can't probe which resume IDs exist."""
    record = resume_repository.get_by_id(db, resume_id)
    if not record or record.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return record


@router.get("")
def list_my_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The current user's resumes, newest first — used to restore a session."""
    records = resume_repository.list_for_user(db, user.user_id)
    return {
        "resumes": [
            {
                "resume_id": r.resume_id,
                "original_filename": r.original_filename,
                "status": r.status,
                "uploaded_at": r.uploaded_at,
            }
            for r in records
        ]
    }


def _to_match_response(r: MatchResult, job: JobRecord | None) -> JobMatchResponse:
    """Single place where a persisted MatchResult row becomes an API response."""
    return JobMatchResponse(
        match_id=r.match_id,
        job_id=r.job_id,
        title=job.title if job else "Unknown",
        company=job.company if job else None,
        location=job.location if job else None,
        apply_url=job.apply_url if job else None,
        blended_score=r.blended_score,
        vector_similarity=r.vector_similarity,
        skill_overlap_ratio=r.skill_overlap_ratio,
        matched_skills=r.matched_skills or [],
        missing_skills=r.missing_skills or [],
        explanation=r.explanation,
        ats_score=r.ats_score if r.ats_score is not None else 0.0,
        ats_found_keywords=r.ats_found_keywords or [],
        ats_missing_keywords=r.ats_missing_keywords or [],
        ats_format_score=r.ats_format_score if r.ats_format_score is not None else 0.0,
        status=r.status,
    )

MAX_FILE_SIZE_MB = 5


def _run_extraction(resume_id: str) -> None:
    """
    Background task fired right after upload: extracts text and updates status.
    Uses its own DB session — the request session is closed by the time this runs.
    """
    db = SessionLocal()
    try:
        record = resume_repository.get_by_id(db, resume_id)
        if not record or record.extracted_text:
            return
        try:
            record.extracted_text = extract_text(record.stored_path)
            record.status = "extracted"
        except ExtractionError as e:
            logger.warning("Extraction failed for resume %s: %s", resume_id, e)
            record.status = "extraction_failed"
        db.commit()
    except Exception:
        # Unexpected failure (DB hiccup etc.) must be visible in logs, never silent.
        logger.exception("Background extraction crashed for resume %s", resume_id)
        db.rollback()
    finally:
        db.close()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()

    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large ({size_mb:.1f} MB). Max {MAX_FILE_SIZE_MB} MB.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_hash = compute_file_hash(content)

    # Dedup check (per-user) — same file uploaded before returns the existing record
    existing = resume_repository.get_by_hash(db, user.user_id, file_hash)
    if existing:
        return ResumeUploadResponse(
            resume_id=existing.resume_id,
            original_filename=existing.original_filename,
            stored_path=existing.stored_path,
            uploaded_at=existing.uploaded_at,
            status="duplicate_of_existing",
        )

    try:
        resume_id, stored_path = save_resume_file(file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        record = resume_repository.create_resume(
            db=db,
            resume_id=resume_id,
            user_id=user.user_id,
            original_filename=file.filename,
            stored_path=stored_path,
            file_hash=file_hash,
        )
    except IntegrityError:
        # Race: same file uploaded concurrently by this user.
        db.rollback()
        existing = resume_repository.get_by_hash(db, user.user_id, file_hash)
        if existing:
            return ResumeUploadResponse(
                resume_id=existing.resume_id,
                original_filename=existing.original_filename,
                stored_path=existing.stored_path,
                uploaded_at=existing.uploaded_at,
                status="duplicate_of_existing",
            )
        raise

    # Kick off extraction automatically — client no longer has to call /extract.
    background_tasks.add_task(_run_extraction, record.resume_id)

    return ResumeUploadResponse(
        resume_id=record.resume_id,
        original_filename=record.original_filename,
        stored_path=record.stored_path,
        uploaded_at=record.uploaded_at,
        status=record.status,
    )


def _extract_resume_text(record, db: Session, force: bool = False):
    resume_id = record.resume_id
    # Idempotent: don't re-read the file if we already have text (unless forced).
    if record.extracted_text and not force:
        return {"resume_id": resume_id, "extracted_text": record.extracted_text, "cached": True}

    try:
        text = extract_text(record.stored_path)
    except ExtractionError as e:
        record.status = "extraction_failed"
        db.commit()
        raise HTTPException(status_code=422, detail=str(e))

    record.extracted_text = text
    record.status = "extracted"
    db.commit()

    return {"resume_id": resume_id, "extracted_text": text, "cached": False}


@router.post("/{resume_id}/extract")
def extract_resume_text(
    resume_id: str,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extracts text from the stored file (idempotent; pass force=true to re-extract)."""
    record = _get_owned_resume(db, resume_id, user)
    return _extract_resume_text(record, db, force=force)


@router.post("/{resume_id}/parse")
def parse_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_resume(db, resume_id, user)

    if not record.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text found. Call /extract first.",
        )

    try:
        parsed, confidence = parse_resume_text(record.extracted_text)
    except ParsingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMRouterError as e:
        raise HTTPException(status_code=502, detail=f"LLM unavailable: {e}")

    parsed = normalize_resume(parsed)  # <-- new step

    record.parsed_data = parsed.model_dump(mode="json")  # JSONB — queryable, no string shim
    record.confidence_score = confidence
    record.status = "parsed"
    db.commit()

    return {
        "resume_id": resume_id,
        "confidence_score": confidence,
        "parsed_resume": parsed.model_dump(),
    }

@router.post("/{resume_id}/embed")
def embed_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_resume(db, resume_id, user)

    if not record.parsed_data:
        raise HTTPException(
            status_code=400,
            detail="No parsed data found. Call /parse first.",
        )

    parsed = ParsedResume(**record.parsed_data)
    summary_text = build_resume_summary_text(parsed)
    vector = generate_embedding(summary_text)

    record.embedding_vector = vector
    db.commit()

    return {
        "resume_id": resume_id,
        "embedding_dim": len(vector),
        "summary_text_used": summary_text,
    }

@router.get("/{resume_id}/shortlist")
def get_job_shortlist(
    resume_id: str,
    top_n: int = 40,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_resume(db, resume_id, user)

    if record.embedding_vector is None:
        raise HTTPException(
            status_code=400,
            detail="No embedding found. Call /embed first.",
        )

    resume_vector = list(record.embedding_vector)
    shortlist = get_shortlist(db, resume_vector, top_n=top_n)

    return {
        "resume_id": resume_id,
        "shortlist_count": len(shortlist),
        "shortlist": [
            {
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "similarity_score": round(score, 4),
            }
            for job, score in shortlist
        ],
    }


@router.post("/{resume_id}/matches/generate", response_model=MatchesResponse)
def generate_matches(
    resume_id: str,
    location_contains: str | None = None,
    min_salary: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_resume(db, resume_id, user)
    if record.embedding_vector is None or not record.parsed_data:
        raise HTTPException(status_code=400, detail="Resume must be parsed and embedded first.")

    resume_vector = list(record.embedding_vector)
    parsed_resume = ParsedResume(**record.parsed_data)
    resume_summary_text = build_resume_summary_text(parsed_resume)

    shortlist = get_shortlist(db, resume_vector, top_n=40)
    ranked = rank_jobs(
        shortlist,
        parsed_resume,
        resume_summary_text,
        resume_raw_text=record.extracted_text or "",
        location_contains=location_contains,
        min_salary=min_salary,
    )

    saved_records = save_match_results(db, resume_id, ranked)

    # Join persisted records back with job metadata (title/company/location/apply_url)
    job_lookup = {j.job_id: j for j, _ in shortlist}
    results = [_to_match_response(r, job_lookup.get(r.job_id)) for r in saved_records]

    return MatchesResponse(resume_id=resume_id, result_count=len(results), results=results)


@router.get("/{resume_id}/matches", response_model=MatchesResponse)
def list_matches(
    resume_id: str,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reads back already-generated matches WITHOUT recomputing anything —
    cheap and instant, unlike /matches/generate which runs the full pipeline.
    Includes the user's saved and dismissed jobs via ?status=saved / ?status=dismissed.
    """
    _get_owned_resume(db, resume_id, user)
    matches = get_matches_for_resume(db, resume_id, status=status)
    job_ids = [m.job_id for m in matches]
    jobs = db.query(JobRecord).filter(JobRecord.job_id.in_(job_ids)).all()
    job_lookup = {j.job_id: j for j in jobs}
    results = [_to_match_response(r, job_lookup.get(r.job_id)) for r in matches]

    return MatchesResponse(resume_id=resume_id, result_count=len(results), results=results)

class MatchStatusUpdate(BaseModel):
    status: str  # "saved" or "dismissed"

@router.patch("/matches/{match_id}/status")
def set_match_status(
    match_id: str,
    body: MatchStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.status not in VALID_MATCH_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of {VALID_MATCH_STATUSES}.",
        )

    # Ownership: the match must belong to one of the current user's resumes.
    match = get_match_by_id(db, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    _get_owned_resume(db, match.resume_id, user)

    record = update_match_status(db, match_id, body.status)
    return {"match_id": match_id, "status": record.status}