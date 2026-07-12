import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
    raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env")

# --- Auth (JWT) ---
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET not set in .env — generate a long random string.")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h default

# --- Optional: production hardening ---
API_KEY = os.getenv("API_KEY")  # unset = auth disabled (local dev)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

# --- Optional: background job sync (scheduler stays off unless queries are set) ---
_sync_queries_raw = os.getenv("JOB_SYNC_QUERIES", "")
JOB_SYNC_QUERIES = [q.strip() for q in _sync_queries_raw.split(";") if q.strip()]
JOB_SYNC_INTERVAL_HOURS = int(os.getenv("JOB_SYNC_INTERVAL_HOURS", "6"))
JOB_SYNC_COUNTRY = os.getenv("JOB_SYNC_COUNTRY", "gb")
