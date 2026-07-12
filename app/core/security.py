"""
API-key authentication.

Opt-in: set API_KEY in .env and every endpoint (except /health and the docs)
requires an `X-API-Key` header. Leave it unset for open local development.
Comparison uses hmac.compare_digest to prevent timing attacks.
"""

import hmac

from fastapi import Header, HTTPException

from app.core.config import API_KEY


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEY:
        return  # auth disabled (local development)
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")
