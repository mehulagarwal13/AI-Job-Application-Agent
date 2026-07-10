from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.file_storage import save_resume_file, compute_file_hash, STORAGE_DIR
from app.services.text_extraction import extract_text, ExtractionError
from app.models.resume import ResumeUploadResponse
from app.core.database import get_db
from app.services import resume_repository
from app.services.resume_parser import parse_resume_text, ParsingError
from app.services.normalizer import normalize_resume

import json
from app.services.resume_text_builder import build_resume_summary_text
from app.services.embedding_service import generate_embedding
from app.models.parsed_resume import ParsedResume
from app.services.matching.retrieval import get_shortlist

from app.services.matching.ranker import rank_jobs
from app.services.resume_text_builder import build_resume_summary_text
from app.models.parsed_resume import ParsedResume

from app.services.match_repository import save_match_results, get_matches_for_resume
from app.models.match_response import MatchesResponse, JobMatchResponse
from app.models.db_models import JobRecord

from app.models.db_models import VALID_MATCH_STATUSES
from app.services.match_repository import update_match_status
from pydantic import BaseModel


router = APIRouter(prefix="/resumes", tags=["resumes"])

MAX_FILE_SIZE_MB = 5

@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()

    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large ({size_mb:.1f} MB). Max {MAX_FILE_SIZE_MB} MB.")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_hash = compute_file_hash(content)

    # Dedup check — if we've seen this exact file before, return the existing record
    existing = resume_repository.get_by_hash(db, file_hash)
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

    record = resume_repository.create_resume(
        db=db,
        resume_id=resume_id,
        original_filename=file.filename,
        stored_path=stored_path,
        file_hash=file_hash,
    )

    return ResumeUploadResponse(
        resume_id=record.resume_id,
        original_filename=record.original_filename,
        stored_path=record.stored_path,
        uploaded_at=record.uploaded_at,
        status=record.status,
    )


@router.get("/{resume_id}/extract")
def extract_resume_text(resume_id: str, db: Session = Depends(get_db)):
    record = resume_repository.get_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found.")

    try:
        text = extract_text(record.stored_path)
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Persist it so Node 4 doesn't need to re-extract every time
    record.extracted_text = text
    db.commit()

    return {"resume_id": resume_id, "extracted_text": text}


@router.post("/{resume_id}/parse")
def parse_resume(resume_id: str, db: Session = Depends(get_db)):
    record = resume_repository.get_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found.")

    if not record.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="No extracted text found. Call /extract first.",
        )

    try:
        parsed, confidence = parse_resume_text(record.extracted_text)
    except ParsingError as e:
        raise HTTPException(status_code=422, detail=str(e))

    parsed = normalize_resume(parsed)  # <-- new step

    record.parsed_data = parsed.model_dump_json()
    record.confidence_score = str(confidence)
    record.status = "parsed"
    db.commit()

    return {
        "resume_id": resume_id,
        "confidence_score": confidence,
        "parsed_resume": parsed.model_dump(),
    }

@router.post("/{resume_id}/embed")
def embed_resume(resume_id: str, db: Session = Depends(get_db)):
    record = resume_repository.get_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found.")

    if not record.parsed_data:
        raise HTTPException(
            status_code=400,
            detail="No parsed data found. Call /parse first.",
        )

    parsed = ParsedResume(**json.loads(record.parsed_data))
    summary_text = build_resume_summary_text(parsed)
    vector = generate_embedding(summary_text)

    record.embedding = json.dumps(vector)
    db.commit()

    return {
        "resume_id": resume_id,
        "embedding_dim": len(vector),
        "summary_text_used": summary_text,
    }

@router.get("/{resume_id}/shortlist")
def get_job_shortlist(resume_id: str, top_n: int = 40, db: Session = Depends(get_db)):
    record = resume_repository.get_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found.")

    if not record.embedding:
        raise HTTPException(
            status_code=400,
            detail="No embedding found. Call /embed first.",
        )

    resume_vector = json.loads(record.embedding)
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
    db: Session = Depends(get_db),
):
    record = resume_repository.get_by_id(db, resume_id)
    if not record:
        raise HTTPException(status_code=404, detail="Resume not found.")
    if not record.embedding or not record.parsed_data:
        raise HTTPException(status_code=400, detail="Resume must be parsed and embedded first.")

    resume_vector = json.loads(record.embedding)
    parsed_resume = ParsedResume(**json.loads(record.parsed_data))
    resume_summary_text = build_resume_summary_text(parsed_resume)

    shortlist = get_shortlist(db, resume_vector, top_n=40)
    ranked = rank_jobs(
        shortlist,
        parsed_resume,
        resume_summary_text,
        resume_raw_text=record.extracted_text,
        location_contains=location_contains,
        min_salary=min_salary,
    )

    saved_records = save_match_results(db, resume_id, ranked)

    # Join persisted records back with job metadata (title/company/location/apply_url)
    job_lookup = {j.job_id: j for j, _ in shortlist}
    results = []
    for r in saved_records:
        job = job_lookup.get(r.job_id)
        results.append(JobMatchResponse(
            match_id=r.match_id,
            job_id=r.job_id,
            title=job.title if job else "Unknown",
            company=job.company if job else None,
            location=job.location if job else None,
            apply_url=job.apply_url if job else None,
            blended_score=float(r.blended_score),
            vector_similarity=float(r.vector_similarity),
            skill_overlap_ratio=float(r.skill_overlap_ratio),
            matched_skills=json.loads(r.matched_skills),
            missing_skills=json.loads(r.missing_skills),
            explanation=r.explanation,
            ats_score=float(r.ats_score) if r.ats_score is not None else 0.0,
            ats_found_keywords=json.loads(r.ats_found_keywords) if r.ats_found_keywords else [],
            ats_missing_keywords=json.loads(r.ats_missing_keywords) if r.ats_missing_keywords else [],
            ats_format_score=float(r.ats_format_score) if r.ats_format_score is not None else 0.0,
            status=r.status,
        ))

    return MatchesResponse(resume_id=resume_id, result_count=len(results), results=results)


@router.get("/{resume_id}/matches", response_model=MatchesResponse)
def list_matches(resume_id: str, status: str | None = None, db: Session = Depends(get_db)):
    """
    Reads back already-generated matches WITHOUT recomputing anything —
    cheap and instant, unlike /matches/generate which runs the full pipeline.
    """
    matches = get_matches_for_resume(db, resume_id, status=status)
    job_ids = [m.job_id for m in matches]
    jobs = db.query(JobRecord).filter(JobRecord.job_id.in_(job_ids)).all()
    job_lookup = {j.job_id: j for j in jobs}

    results = []
    for r in matches:
        job = job_lookup.get(r.job_id)
        results.append(JobMatchResponse(
            match_id=r.match_id,
            job_id=r.job_id,
            title=job.title if job else "Unknown",
            company=job.company if job else None,
            location=job.location if job else None,
            apply_url=job.apply_url if job else None,
            blended_score=float(r.blended_score),
            vector_similarity=float(r.vector_similarity),
            skill_overlap_ratio=float(r.skill_overlap_ratio),
            matched_skills=json.loads(r.matched_skills),
            missing_skills=json.loads(r.missing_skills),
            explanation=r.explanation,
            ats_score=float(r.ats_score) if r.ats_score is not None else 0.0,
            ats_found_keywords=json.loads(r.ats_found_keywords) if r.ats_found_keywords else [],
            ats_missing_keywords=json.loads(r.ats_missing_keywords) if r.ats_missing_keywords else [],
            ats_format_score=float(r.ats_format_score) if r.ats_format_score is not None else 0.0,
            status=r.status,
        ))

    return MatchesResponse(resume_id=resume_id, result_count=len(results), results=results)

class MatchStatusUpdate(BaseModel):
    status: str  # "saved" or "dismissed"

@router.patch("/matches/{match_id}/status")
def set_match_status(match_id: str, body: MatchStatusUpdate, db: Session = Depends(get_db)):
    if body.status not in VALID_MATCH_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of {VALID_MATCH_STATUSES}.",
        )

    record = update_match_status(db, match_id, body.status)
    if not record:
        raise HTTPException(status_code=404, detail="Match not found.")

    return {"match_id": match_id, "status": record.status}