import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, resumes, jobs
from app.core.auth import get_current_user
from app.core.config import CORS_ORIGINS
from app.core.database import Base, engine
from app.core.middleware import register_middleware
from app.core.pgvector_setup import ensure_pgvector_extension, ensure_vector_schema
from app.core.scheduler import start_scheduler
from app.models import db_models  # noqa: F401 — registers models on Base.metadata

# Basic structured-ish logging so warnings (LLM retries, extraction failures) surface.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Database bootstrap -----------------------------------------------------
# NOTE: Alembic is the source of truth for schema (alembic upgrade head).
# create_all is kept as a convenience for first-run local setups; it only
# creates missing tables and never alters existing ones.
try:
    ensure_pgvector_extension()   # must precede create_all (vector column type)
    Base.metadata.create_all(bind=engine)
    ensure_vector_schema()        # idempotent column backfill + HNSW index
except Exception:
    logger.critical(
        "Database bootstrap failed. Check DATABASE_URL in .env — it must be a "
        "valid Neon connection string (postgresql://...neon.tech/...?sslmode=require)."
    )
    raise

start_scheduler()                 # no-op unless JOB_SYNC_QUERIES is set in .env

# --- App --------------------------------------------------------------------
app = FastAPI(title="AI Job Application Agent", version="1.0.0")

register_middleware(app)          # rate limiting, request logging, error safety net

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Auth endpoints are public; all business routes require a logged-in user (JWT).
app.include_router(auth.router)
app.include_router(resumes.router)  # endpoints take the user dependency individually
app.include_router(jobs.router, dependencies=[Depends(get_current_user)])


@app.get("/health")
def health_check():
    """Liveness + DB reachability."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}
