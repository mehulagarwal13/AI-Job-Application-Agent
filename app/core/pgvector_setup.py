"""
pgvector bootstrap for Neon.

Neon ships with the pgvector extension available but not enabled per-database.
Call order at startup (see app/main.py):
  1. ensure_pgvector_extension()  — must run BEFORE create_all, since the
     jobs.embedding_vector column uses the `vector` type.
  2. Base.metadata.create_all(...)
  3. ensure_vector_schema()       — idempotent ALTER/INDEX for databases that
     were created before this column existed, plus the HNSW search index.
"""

import logging

from sqlalchemy import text

from app.core.database import engine
from app.models.db_models import EMBEDDING_DIM

logger = logging.getLogger(__name__)


def ensure_pgvector_extension() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    logger.info("pgvector extension ready")


def ensure_vector_schema() -> None:
    with engine.begin() as conn:
        # Covers pre-existing databases created before the columns were added.
        conn.execute(text(
            f"ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding_vector vector({EMBEDDING_DIM})"
        ))
        conn.execute(text(
            f"ALTER TABLE resumes ADD COLUMN IF NOT EXISTS embedding_vector vector({EMBEDDING_DIM})"
        ))
        # HNSW index: fast approximate nearest-neighbor search with cosine distance.
        # Embeddings are L2-normalized, so cosine ordering == dot-product ordering.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_jobs_embedding_vector_hnsw "
            "ON jobs USING hnsw (embedding_vector vector_cosine_ops)"
        ))
        # Cross-source dedup key (Phase 3) — same idempotent-upgrade pattern.
        conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS dedup_key VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_dedup_key ON jobs (dedup_key)"))
        # Auth upgrade: per-user resumes; file_hash dedup became per-user (unique index dropped).
        conn.execute(text("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS user_id VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_resumes_user_id ON resumes (user_id)"))
        conn.execute(text("DROP INDEX IF EXISTS ix_resumes_file_hash"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_resumes_file_hash ON resumes (file_hash)"))
    logger.info("vector columns, HNSW index, dedup_key, and user ownership columns ready")
