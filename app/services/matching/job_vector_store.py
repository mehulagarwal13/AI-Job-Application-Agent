"""
Vector search over jobs — pgvector on Neon.

Replaces the previous Qdrant-backed implementation. Vectors live in the
jobs.embedding_vector column (see app/models/db_models.py), indexed with HNSW.
Similarity search is a single SQL query — no external vector service, no
separate ID mapping, and results arrive as full JobRecord rows already.
"""

from sqlalchemy.orm import Session

from app.models.db_models import JobRecord


def search_similar_jobs(
    db: Session,
    query_vector: list[float],
    top_n: int = 40,
) -> list[tuple[JobRecord, float]]:
    """
    Returns [(JobRecord, similarity_score)] sorted by similarity descending.

    pgvector's <=> operator is cosine *distance*; similarity = 1 - distance.
    Embeddings are normalized, so this is equivalent to dot-product ranking.
    """
    distance = JobRecord.embedding_vector.cosine_distance(query_vector)

    rows = (
        db.query(JobRecord, (1 - distance).label("similarity"))
        .filter(JobRecord.embedding_vector.isnot(None))
        .order_by(distance)
        .limit(top_n)
        .all()
    )
    return [(job, float(similarity)) for job, similarity in rows]
