"""API key authentication and CORS configuration.

The POC mounted CORSMiddleware with allow_origins=["*"] and left every endpoint
unauthenticated, so any origin could start negotiations -- each of which costs
LLM calls -- and read any transaction by guessing its id.

Posture:
  * CORS origins come from ALLOWED_ORIGINS (comma-separated). The default is the
    local dev servers rather than "*", so a deployment has to opt in to being
    open instead of opting out.
  * If API_KEY is set, mutating endpoints require a matching X-API-Key header.
    If it is unset the service runs open and logs a warning at startup -- the
    local demo keeps working, but an unprotected deployment is never silent.
"""

import logging
import os
import secrets

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"


def allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        logger.warning(
            "ALLOWED_ORIGINS is '*' — every origin may call this API. "
            "Set it to your UI origin before deploying."
        )
    return origins


def api_key_configured() -> bool:
    return bool(os.getenv("API_KEY"))


def warn_if_unprotected() -> None:
    if not api_key_configured():
        logger.warning(
            "API_KEY is not set — negotiation endpoints are unauthenticated. "
            "Anyone who can reach this service can spend LLM budget on it."
        )


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency guarding mutating endpoints.

    No-ops when API_KEY is unset so the local demo needs no configuration.
    """
    expected = os.getenv("API_KEY")
    if not expected:
        return

    # Constant-time comparison: a plain == leaks key material through timing.
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
