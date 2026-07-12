# REMOVED — Qdrant was replaced by pgvector on Neon.
# Vector storage/search now lives in:
#   - app/models/db_models.py        (jobs.embedding_vector column)
#   - app/core/pgvector_setup.py     (extension + HNSW index bootstrap)
#   - app/services/matching/job_vector_store.py (similarity search)
# This file is kept only to avoid breaking stale imports; delete it freely.
