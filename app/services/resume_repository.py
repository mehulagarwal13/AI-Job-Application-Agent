from sqlalchemy.orm import Session
from app.models.db_models import ResumeRecord


def get_by_hash(db: Session, user_id: str, file_hash: str) -> ResumeRecord | None:
    """Dedup is per-user: the same file uploaded by two users is two records."""
    return (
        db.query(ResumeRecord)
        .filter(ResumeRecord.user_id == user_id, ResumeRecord.file_hash == file_hash)
        .first()
    )


def get_by_id(db: Session, resume_id: str) -> ResumeRecord | None:
    return db.query(ResumeRecord).filter(ResumeRecord.resume_id == resume_id).first()


def list_for_user(db: Session, user_id: str) -> list[ResumeRecord]:
    return (
        db.query(ResumeRecord)
        .filter(ResumeRecord.user_id == user_id)
        .order_by(ResumeRecord.uploaded_at.desc())
        .all()
    )


def create_resume(
    db: Session,
    resume_id: str,
    user_id: str,
    original_filename: str,
    stored_path: str,
    file_hash: str,
) -> ResumeRecord:
    record = ResumeRecord(
        resume_id=resume_id,
        user_id=user_id,
        original_filename=original_filename,
        stored_path=stored_path,
        file_hash=file_hash,
        status="uploaded",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
