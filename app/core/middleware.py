"""
Production middleware: request logging, rate limiting, global error handling.

Rate limiter: in-memory sliding window per client IP. Correct for a single
process (this project's deployment model — uvicorn, no Docker/k8s). If you
ever scale to multiple processes, swap the counter store for Redis; the
middleware interface stays identical.
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import RATE_LIMIT_PER_MINUTE

logger = logging.getLogger("app.request")

_WINDOW_SECONDS = 60
_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

# ip -> deque of request timestamps within the current window
_hits: dict[str, deque] = defaultdict(deque)
_MAX_TRACKED_IPS = 10_000  # prune threshold so the map can't grow unbounded


def _prune_idle_ips(now: float) -> None:
    if len(_hits) <= _MAX_TRACKED_IPS:
        return
    for ip in [ip for ip, window in _hits.items()
               if not window or now - window[-1] > _WINDOW_SECONDS]:
        del _hits[ip]


def _is_rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    _prune_idle_ips(now)
    window = _hits[client_ip]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return True
    window.append(now)
    return False


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_pipeline(request: Request, call_next):
        # --- rate limiting ---
        if request.url.path not in _EXEMPT_PATHS:
            client_ip = request.client.host if request.client else "unknown"
            if _is_rate_limited(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again shortly."},
                )

        # --- timing + logging + last-resort error handling ---
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Nothing unhandled ever leaks a stack trace to the client.
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error."},
            )

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.0fms)",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response
