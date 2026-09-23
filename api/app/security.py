import hashlib
import ipaddress
import math
import secrets
import time
from collections import deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from email_validator import EmailNotValidError, validate_email
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.errors import ApiError, error_response

_hasher = PasswordHasher()
# Verified against when the account does not exist, so timing does not reveal it.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def new_token() -> tuple[str, bytes]:
    """Opaque token for the client and its sha256 for the database."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def normalize_email(raw: str) -> str:
    try:
        return validate_email(raw.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ApiError(400, "invalid_email") from None


def check_password_policy(password: str, email: str | None) -> None:
    if not 10 <= len(password) <= 128 or (email and password.strip().lower() == email.lower()):
        raise ApiError(400, "weak_password")


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hasher.hash, password)


async def verify_password(stored: str | None, password: str) -> bool:
    """Constant-ish time check; returns False for a missing hash too."""

    def check() -> bool:
        try:
            return _hasher.verify(stored or _DUMMY_HASH, password) and stored is not None
        except (VerificationError, InvalidHashError):
            return False

    if len(password) > 128:
        return False
    return await run_in_threadpool(check)


def needs_rehash(stored: str) -> bool:
    return _hasher.check_needs_rehash(stored)


def client_host(request: Request) -> str:
    """Peer address as uvicorn sees it (X-Forwarded-For is applied by --proxy-headers)."""
    return request.client.host if request.client else "unknown"


def client_ip(request: Request) -> str | None:
    """Same, but only if it is a valid IP, for inet columns."""
    try:
        return str(ipaddress.ip_address(client_host(request)))
    except ValueError:
        return None


class RateLimiter:
    """Sliding-window counter per key, in process memory (one api replica)."""

    LIMITS = {
        "login": (10, 15 * 60),
        "email_check": (20, 15 * 60),
        "register": (5, 60 * 60),
        "forgot": (3, 60 * 60),
        "passkey": (20, 15 * 60),
    }

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def hit(self, bucket: str, *keys: str | None) -> None:
        limit, window = self.LIMITS[bucket]
        now = time.monotonic()
        if len(self._hits) > 50_000:
            self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - 3600}
        for key in filter(None, keys):
            q = self._hits.setdefault(f"{bucket}:{key}", deque())
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                retry = math.ceil(q[0] + window - now)
                raise ApiError(
                    429, "rate_limited", headers={"Retry-After": str(retry)}, retry_after=retry
                )
            q.append(now)


limiter = RateLimiter()


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """CSRF guard: state-changing /api/* requests must come from our own origin."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and request.url.path.startswith("/api/")
            and request.headers.get("origin") != get_settings().public_origin
        ):
            return error_response(403, "bad_origin")
        return await call_next(request)
