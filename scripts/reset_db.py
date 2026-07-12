"""
One-time database reset: drops all app tables and recreates them from the
current models. Use when the schema changed and the DB predates it.

    python scripts/reset_db.py

DESTRUCTIVE — wipes resumes, jobs, and match_results. Asks for confirmation.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, engine  # noqa: E402
from app.core.pgvector_setup import ensure_pgvector_extension, ensure_vector_schema  # noqa: E402
from app.models import db_models  # noqa: F401, E402 — registers models


def main() -> None:
    answer = input("This DROPS resumes, jobs, and match_results on the target DB. Type 'yes' to continue: ")
    if answer.strip().lower() != "yes":
        print("Aborted.")
        return

    ensure_pgvector_extension()
    print("Dropping tables...")
    Base.metadata.drop_all(bind=engine)
    print("Recreating with current schema...")
    Base.metadata.create_all(bind=engine)
    ensure_vector_schema()
    print("Done. Restart the app and re-upload/re-ingest.")


if __name__ == "__main__":
    main()
