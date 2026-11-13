import asyncio
import smtplib
import ssl
import time
from uuid import uuid4

import pytest

from app import mailer
from tests.conftest import register, run_sql


def deliver(client, settings, concurrent=False):
    async def go():
        saved = settings.smtp_host
        settings.smtp_host = "smtp.example.com"
        try:
            if concurrent:
                return await asyncio.gather(mailer.deliver_one(), mailer.deliver_one())
            return await mailer.deliver_one()
        finally:
            settings.smtp_host = saved

    return client.portal.call(go)


def queue_row():
    return run_sql("select * from web.outbox order by id desc limit 1")[0]


def test_retry_after_failure(client, test_settings, monkeypatch):
    register(client)
    calls = []

    def smtp(*args):
        calls.append(args)
        if len(calls) == 1:
            raise smtplib.SMTPServerDisconnected("private provider response")

    monkeypatch.setattr(mailer, "_smtp_send", smtp)
    assert deliver(client, test_settings)
    row = queue_row()
    assert row["attempts"] == 1 and row["sent_at"] is None
    assert row["last_error"] == "SMTPServerDisconnected"
    assert row["lease_token"] is None
    assert not deliver(client, test_settings)
    run_sql("update web.outbox set next_attempt_at=now()", fetch=False)
    assert deliver(client, test_settings)
    row = queue_row()
    assert row["attempts"] == 2 and row["sent_at"] is not None
    assert row["last_error"] is None
    assert calls[0][3] == calls[1][3]


def test_concurrent_workers_send_once(client, test_settings, monkeypatch):
    register(client)
    calls = []

    def smtp(*args):
        calls.append(args)
        time.sleep(0.05)

    monkeypatch.setattr(mailer, "_smtp_send", smtp)
    assert sorted(deliver(client, test_settings, concurrent=True)) == [False, True]
    assert len(calls) == 1


@pytest.mark.parametrize("reason", ["expired", "used", "email_changed"])
def test_invalid_link_not_delivered(client, test_settings, monkeypatch, reason):
    register(client)
    sql = {
        "expired": "update web.auth_tokens set expires_at=now()-interval '1 second'",
        "used": "update web.auth_tokens set used_at=now()",
        "email_changed": "update web.accounts set email='changed@example.com'",
    }[reason]
    run_sql(sql, fetch=False)
    calls = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda *args: calls.append(args))
    assert deliver(client, test_settings)
    assert not calls
    assert queue_row()["discarded_at"] is not None


def test_expired_lease_recovers_legacy_mail(client, test_settings, monkeypatch):
    register(client)
    run_sql(
        "update web.outbox set token_hash=null,lease_token=gen_random_uuid(),"
        "lease_until=now()-interval '1 second'",
        fetch=False,
    )
    calls = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda *args: calls.append(args))
    assert deliver(client, test_settings)
    assert len(calls) == 1
    assert queue_row()["sent_at"] is not None


def test_retry_limit(client, test_settings, monkeypatch):
    register(client)
    run_sql("update web.outbox set attempts=8", fetch=False)
    calls = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda *args: calls.append(args))
    assert not deliver(client, test_settings)
    assert not calls


@pytest.mark.parametrize("port", [465, 587])
def test_smtp_verifies_tls_and_recipient(port, monkeypatch):
    from app.config import Settings

    settings = Settings(
        smtp_host="smtp.example.com",
        smtp_port=port,
        smtp_user="sender@example.com",
        smtp_password="test-only",
    )
    monkeypatch.setattr(mailer, "get_settings", lambda: settings)
    contexts, messages, starts = [], [], []

    class Transport:
        def __init__(self, host, port, **kwargs):
            if "context" in kwargs:
                contexts.append(kwargs["context"])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context):
            starts.append(True)
            contexts.append(context)

        def login(self, user, password):
            assert user == settings.smtp_user

        def send_message(self, msg):
            messages.append(msg)
            return {"receiver@example.com": (550, b"refused")}

    monkeypatch.setattr(mailer.smtplib, "SMTP", Transport)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", Transport)
    key = uuid4()
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        mailer._smtp_send("receiver@example.com", "subject", "body", key)
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED and contexts[0].check_hostname
    assert bool(starts) == (port == 587)
    assert messages[0]["Message-ID"] == f"<crs-vpn-{key}@example.com>"
