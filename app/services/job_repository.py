from sqlalchemy.orm import Session
from app.models.db_models import JobRecord


def get_by_job_id(db: Session, job_id: str) -> JobRecord | None:
    return db.query(JobRecord).filter(JobRecord.job_id == job_id).first()


def get_by_dedup_key(db: Session, dedup_key: str) -> JobRecord | None:
    return db.query(JobRecord).filter(JobRecord.dedup_key == dedup_key).first()


def upsert_job(db: Session, job_dict: dict) -> JobRecord:
    existing = get_by_job_id(db, job_dict["job_id"])
    if existing:
        # Refresh metadata. If the description text changed, the cached vector
        # no longer represents the job — clear it so /embed-pending re-embeds.
        if job_dict["description"] != existing.description:
            existing.embedding_vector = None
        existing.title = job_dict["title"]
        existing.company = job_dict["company"]
        existing.location = job_dict["location"]
        existing.description = job_dict["description"]
        existing.salary_min = job_dict["salary_min"]
        existing.salary_max = job_dict["salary_max"]
        existing.apply_url = job_dict["apply_url"]
        existing.min_years_required = job_dict["min_years_required"]
        existing.remote = job_dict.get("remote")
        existing.dedup_key = job_dict.get("dedup_key")
        db.commit()
        db.refresh(existing)
        return existing

    record = JobRecord(**job_dict)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_unembedded_jobs(db: Session) -> list[JobRecord]:
    return db.query(JobRecord).filter(JobRecord.embedding_vector.is_(None)).all()


def list_all_jobs(db: Session) -> list[JobRecord]:
    return db.query(JobRecord).all()