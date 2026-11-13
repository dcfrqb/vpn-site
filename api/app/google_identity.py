"""Verify Google signatures/audience/expiry; never identify users by email alone."""

import asyncio
import hmac
from functools import partial

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.errors import ApiError
from app.security import normalize_email


def _verify(token: str, client_id: str) -> dict:
    transport = Request()
    try:
        return id_token.verify_oauth2_token(token, partial(transport, timeout=5), client_id)
    finally:
        transport.session.close()


async def verify(token: str, client_id: str, nonce: str) -> dict:
    try:
        claims = await asyncio.to_thread(_verify, token, client_id)
    except TransportError:
        raise ApiError(503, "google_unavailable") from None
    except (ValueError, GoogleAuthError):
        raise ApiError(401, "google_invalid") from None
    sub = claims.get("sub")
    token_nonce = claims.get("nonce")
    email = claims.get("email")
    if (
        not isinstance(sub, str)
        or not sub
        or len(sub) > 255
        or not isinstance(token_nonce, str)
        or not hmac.compare_digest(token_nonce.encode(), nonce.encode())
        or not isinstance(email, str)
        or claims.get("email_verified") is not True
    ):
        raise ApiError(401, "google_invalid")
    try:
        email = normalize_email(email)
    except ApiError:
        raise ApiError(401, "google_invalid") from None
    # Google does not guarantee continued ownership of a third-party email address.
    authoritative = email.endswith("@gmail.com") or bool(claims.get("hd"))
    return {"sub": sub, "email": email, "authoritative": authoritative}
