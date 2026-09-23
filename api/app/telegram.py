"""Telegram Login Widget payload check (core.telegram.org/widgets/login#checking-authorization)."""

import hashlib
import hmac
import time

from app.config import get_settings
from app.errors import ApiError

MAX_AGE = 24 * 60 * 60


def verify_widget(data: dict) -> None:
    token = get_settings().telegram_login_bot_token
    if not token:
        raise ApiError(503, "telegram_unavailable")
    fields = {k: v for k, v in data.items() if k != "hash" and v is not None}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(data.get("hash", ""))):
        raise ApiError(401, "telegram_invalid")
    age = time.time() - int(data["auth_date"])
    if age > MAX_AGE:
        raise ApiError(401, "telegram_expired")
    if age < -300:
        raise ApiError(401, "telegram_invalid")
