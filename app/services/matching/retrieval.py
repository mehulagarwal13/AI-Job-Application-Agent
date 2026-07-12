from sqlalchemy.orm import Session

from app.models.db_models import JobRecord
from app.services.matching.job_vector_store import search_similar_jobs


def get_shortlist(
    db: Session,
    resume_embedding: list[float],
    top_n: int = 40,
) -> list[tuple[JobRecord, float]]:
    """
    Retrieves the top_n most similar jobs via pgvector's indexed search.
    Single SQL query — the old two-step (vector service -> fetch rows) is gone.
    """
    return search_similar_jobs(db, resume_embedding, top_n=top_n)
