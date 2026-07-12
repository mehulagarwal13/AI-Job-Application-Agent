"""
Test bootstrap: guarantees required env vars exist BEFORE any app module is
imported (app.core.config fails fast on missing keys). Values are only
defaults — a real .env on the dev machine takes precedence.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ADZUNA_APP_ID", "test-id")
os.environ.setdefault("ADZUNA_APP_KEY", "test-key")
