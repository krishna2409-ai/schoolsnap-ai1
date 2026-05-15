"""Rate limiting middleware for production"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import os

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

RATE_LIMIT_STRING = f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW_SECONDS}seconds"


def get_rate_limit() -> str:
    """Get rate limit string"""
    if not RATE_LIMIT_ENABLED:
        return "unlimited"
    return RATE_LIMIT_STRING


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exception handler"""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail.split()[-1] if exc.detail else "60"
        }
    )


# Common rate limit presets
RATE_LIMITS = {
    "auth": "5/1minute",  # Strict for auth endpoints
    "upload": "10/1hour",  # Moderate for file uploads
    "default": RATE_LIMIT_STRING,
    "search": "20/1minute",  # Moderate for search
}
