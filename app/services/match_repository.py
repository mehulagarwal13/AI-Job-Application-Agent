import uuid
from sqlalchemy.orm import Session
from app.models.db_models import MatchResult


def save_match_results(db: Session, resume_id: str, ranked_jobs: list[dict]) -> list[MatchResult]:
    """
    Persists a fresh batch of ranked results for a resume.
    Clears out any previous 'new' matches for this resume first, so re-running
    matching doesn't accumulate stale duplicates — but preserves anything
    the user already saved or dismissed (that's a deliberate decision).
    """
    db.query(MatchResult).filter(
        MatchResult.resume_id == resume_id,
        MatchResult.status == "new",
    ).delete()

    records = []
    for job in ranked_jobs:
        record = MatchResult(
            match_id=str(uuid.uuid4()),
            resume_id=resume_id,
            job_id=job["job_id"],
            vector_similarity=job["vector_similarity"],
            skill_overlap_ratio=job["skill_overlap_ratio"],
            blended_score=job["blended_score"],
            matched_skills=job["matched_skills"],
            missing_skills=job["missing_skills"],
            explanation=job["explanation"],
            ats_score=job["ats_score"],
            ats_found_keywords=job["ats_found_keywords"],
            ats_missing_keywords=job["ats_missing_keywords"],
            ats_format_score=job["ats_format_score"],
            status="new",
        )
        db.add(record)
        records.append(record)

    db.commit()
    for r in records:
        db.refresh(r)
    return records


def get_matches_for_resume(db: Session, resume_id: str, status: str | None = None) -> list[MatchResult]:
    query = db.query(MatchResult).filter(MatchResult.resume_id == resume_id)
    if status:
        query = query.filter(MatchResult.status == status)
    return query.order_by(MatchResult.blended_score.desc()).all()


def get_match_by_id(db: Session, match_id: str) -> MatchResult | None:
    return db.query(MatchResult).filter(MatchResult.match_id == match_id).first()


def update_match_status(db: Session, match_id: str, new_status: str) -> MatchResult | None:
    record = db.query(MatchResult).filter(MatchResult.match_id == match_id).first()
    if not record:
        return None
    record.status = new_status
    db.commit()
    db.refresh(record)
    return record