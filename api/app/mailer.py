"""Mail goes to web.outbox first; SMTP delivery only when SMTP_HOST is set."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app import db
from app.config import get_settings

log = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def verify_link(token: str) -> str:
    return f"{get_settings().public_origin}/verify?token={token}"


def reset_link(token: str) -> str:
    return f"{get_settings().public_origin}/reset?token={token}"


VERIFY = (
    "Подтверди email",
    "Привет!\n\nЧтобы подтвердить email в CRS VPN, открой ссылку:\n{link}\n\n"
    "Ссылка действует 24 часа. Если это был не ты, просто не обращай внимания на письмо.",
)
RESET = (
    "Сброс пароля",
    "Привет!\n\nКто-то (надеемся, ты) попросил сбросить пароль в CRS VPN. "
    "Новый пароль можно задать по ссылке:\n{link}\n\n"
    "Ссылка действует 1 час и сработает один раз. Если это был не ты, ничего не делай, "
    "пароль останется прежним.",
)


async def send(conn, to: str, template: tuple[str, str], link: str) -> None:
    subject, body = template[0], template[1].format(link=link)
    mail_id = await conn.fetchval(
        "insert into web.outbox (to_email, subject, body) values ($1, $2, $3) returning id",
        to,
        subject,
        body,
    )
    if not get_settings().smtp_host:
        log.info("mail %s queued in outbox, SMTP is not configured", mail_id)
        return
    task = asyncio.get_running_loop().create_task(_deliver(mail_id, to, subject, body))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _smtp_send(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from or s.smtp_user, to, subject
    msg.set_content(body)
    cls = smtplib.SMTP_SSL if s.smtp_port == 465 else smtplib.SMTP
    with cls(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if cls is smtplib.SMTP:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


async def _deliver(mail_id: int, to: str, subject: str, body: str) -> None:
    try:
        await asyncio.to_thread(_smtp_send, to, subject, body)
    except (OSError, smtplib.SMTPException):
        log.exception("mail %s: SMTP delivery failed, it stays in outbox", mail_id)
        return
    if db.pool is not None:
        await db.pool.execute("update web.outbox set sent_at = now() where id = $1", mail_id)
