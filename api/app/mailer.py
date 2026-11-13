"""Durable authentication mail queue, verified TLS, bounded retry and expiring links."""

import asyncio
import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from app import db
from app.config import get_settings
from app.security import hash_token

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 8


def verify_link(token: str) -> str:
    return f"{get_settings().public_origin}/verify?token={token}"


def reset_link(token: str) -> str:
    return f"{get_settings().public_origin}/reset?token={token}"


VERIFY = (
    "Подтверди email",
    "Привет!\n\nЧтобы подтвердить email в CRS VPN, открой ссылку:\n{link}\n\n"
    "Ссылка действует 24 часа и сработает один раз. "
    "Если ты не создавал аккаунт, ничего не делай.\n\nПоддержка: dcfrqb@gmail.com\n",
)
RESET = (
    "Сброс пароля",
    "Привет!\n\nПолучен запрос на сброс пароля в CRS VPN. "
    "Новый пароль можно задать по ссылке:\n{link}\n\n"
    "Ссылка действует 1 час и сработает один раз. Если это был не ты, ничего не делай, "
    "пароль останется прежним.\n\nПоддержка: dcfrqb@gmail.com\n",
)


def _link_token(link: str) -> bytes | None:
    value = parse_qs(urlsplit(link).query).get("token", [])
    return hash_token(value[0]) if len(value) == 1 and 1 <= len(value[0]) <= 256 else None


async def send(conn, to: str, template: tuple[str, str], link: str) -> None:
    """Enqueue in the caller's transaction. Delivery starts only after commit."""
    subject, body = template[0], template[1].format(link=link)
    await conn.execute(
        "insert into web.outbox (to_email, subject, body, token_hash) values ($1, $2, $3, $4)",
        to,
        subject,
        body,
        _link_token(link),
    )


def _smtp_send(to: str, subject: str, body: str, delivery_key) -> None:
    s = get_settings()
    sender = s.smtp_from or s.smtp_user
    domain = parseaddr(sender)[1].rpartition("@")[2] or "vpn.crs-projects.com"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg["Message-ID"] = f"<crs-vpn-{delivery_key}@{domain}>"
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(body)
    context = ssl.create_default_context()
    if s.smtp_port == 465:
        transport = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=context)
    else:
        transport = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
    with transport as smtp:
        if s.smtp_port != 465:
            smtp.starttls(context=context)
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        refused = smtp.send_message(msg)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


async def _claim():
    if db.pool is None:
        return None
    async with db.pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            "select * from web.outbox where sent_at is null and discarded_at is null"
            " and attempts < $1 and next_attempt_at <= now()"
            " and (lease_until is null or lease_until < now())"
            " order by id for update skip locked limit 1",
            MAX_ATTEMPTS,
        )
        if row is None:
            return None
        # Legacy unsent rows predate token_hash. Recover only an owned valid link,
        # not arbitrary URLs in an old message body.
        token_hash = row["token_hash"]
        if token_hash is None:
            for word in row["body"].split():
                if word.startswith(get_settings().public_origin.rstrip("/") + "/"):
                    token_hash = _link_token(word)
                    if token_hash:
                        break
        valid = token_hash and await conn.fetchval(
            "select exists(select 1 from web.auth_tokens t join web.accounts a"
            " on a.id=t.account_id where t.token_hash=$1 and t.used_at is null"
            " and t.expires_at>now() and t.email=a.email and t.email=$2)",
            token_hash,
            row["to_email"],
        )
        if not valid:
            await conn.execute(
                "update web.outbox set discarded_at=now(),last_error='link_expired_or_used'"
                " where id=$1",
                row["id"],
            )
            return False
        lease = uuid4()
        await conn.execute(
            "update web.outbox set attempts=attempts+1,lease_until=now()+interval '5 minutes',"
            " lease_token=$2,token_hash=$3 where id=$1",
            row["id"],
            lease,
            token_hash,
        )
        return {**dict(row), "lease_token": lease, "attempts": row["attempts"] + 1}


async def deliver_one() -> bool:
    """True means a queue row was handled, False means idle/disabled."""
    if not get_settings().smtp_host or db.pool is None:
        return False
    row = await _claim()
    if row is None:
        return False
    if row is False:
        return True
    try:
        await asyncio.to_thread(
            _smtp_send, row["to_email"], row["subject"], row["body"], row["delivery_key"]
        )
    except (OSError, smtplib.SMTPException) as exc:
        # SMTP error text can include addresses or provider responses; store type only.
        code = type(exc).__name__
        delay = timedelta(seconds=min(3600, 30 * 2 ** (row["attempts"] - 1)))
        await db.pool.execute(
            "update web.outbox set lease_until=null,lease_token=null,last_error=$3,"
            " next_attempt_at=now()+$4::interval where id=$1 and lease_token=$2",
            row["id"],
            row["lease_token"],
            code,
            delay,
        )
        log.warning("mail %s: delivery failed (%s), attempt %s", row["id"], code, row["attempts"])
        return True
    await db.pool.execute(
        "update web.outbox set sent_at=now(),lease_until=null,lease_token=null,last_error=null"
        " where id=$1 and lease_token=$2",
        row["id"],
        row["lease_token"],
    )
    return True


async def delivery_loop():
    while True:
        try:
            # Bounded batch, so stale legacy rows cannot monopolize the event loop.
            for _ in range(20):
                if not await deliver_one():
                    break
        except Exception as exc:
            log.warning("mail worker: %s", type(exc).__name__)
        await asyncio.sleep(5)
