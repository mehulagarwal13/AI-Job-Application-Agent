from sqlalchemy import Column, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

from app.core.database import Base

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size

VALID_MATCH_STATUSES = {"new", "saved", "dismissed"}


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)  # salted PBKDF2, never plaintext
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ResumeRecord(Base):
    __tablename__ = "resumes"

    resume_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    # Dedup is per-user (same file from two users = two records), so no unique constraint.
    file_hash = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="uploaded")  # uploaded/extracted/extraction_failed/parsed
    extracted_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    parsed_data = Column(JSONB, nullable=True)            # structured ParsedResume — queryable JSONB
    confidence_score = Column(Float, nullable=True)
    embedding_vector = Column(Vector(EMBEDDING_DIM), nullable=True)  # pgvector


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)            # "{source}_{source_id}"
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    remote = Column(String, nullable=True)               # "yes"/"no"/None (unknown)
    apply_url = Column(String, nullable=True)
    source = Column(String, nullable=False, default="adzuna")
    dedup_key = Column(String, nullable=True, index=True)  # sha1(title|company) — cross-source dedup
    embedding_vector = Column(Vector(EMBEDDING_DIM), nullable=True)  # searched via HNSW index
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    min_years_required = Column(Float, nullable=True)


class MatchResult(Base):
    __tablename__ = "match_results"

    match_id = Column(String, primary_key=True)
    resume_id = Column(
        String,
        ForeignKey("resumes.resume_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        String,
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vector_similarity = Column(Float, nullable=False)
    skill_overlap_ratio = Column(Float, nullable=False)
    blended_score = Column(Float, nullable=False)         # numeric — sorts correctly
    matched_skills = Column(JSONB, nullable=False)
    missing_skills = Column(JSONB, nullable=False)
    explanation = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="new")  # new/saved/dismissed
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ats_score = Column(Float, nullable=True)
    ats_found_keywords = Column(JSONB, nullable=True)
    ats_missing_keywords = Column(JSONB, nullable=True)
    ats_format_score = Column(Float, nullable=True)
