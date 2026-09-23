"""WebAuthn ceremonies (py_webauthn) with one-use challenges stored in web.webauthn_challenges."""

from datetime import timedelta
from uuid import UUID

import asyncpg
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json_dict, parse_authentication_credential_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import get_settings
from app.errors import ApiError

CHALLENGE_TTL = timedelta(minutes=5)
_BAD_INPUT = (WebAuthnException, ValueError, KeyError, TypeError, AttributeError)


async def _store_challenge(conn, challenge: bytes, kind: str, account_id: UUID | None) -> UUID:
    await conn.execute("delete from web.webauthn_challenges where expires_at < now()")
    return await conn.fetchval(
        "insert into web.webauthn_challenges (challenge, account_id, kind, expires_at)"
        " values ($1, $2, $3, now() + $4::interval) returning id",
        challenge,
        account_id,
        kind,
        CHALLENGE_TTL,
    )


async def _take_challenge(conn, challenge_id: UUID, kind: str, account_id: UUID | None) -> bytes:
    """Deletes the challenge whatever happens next: each one is good for a single attempt."""
    challenge = await conn.fetchval(
        "delete from web.webauthn_challenges where id = $1 and kind = $2"
        " and account_id is not distinct from $3 and expires_at > now() returning challenge",
        challenge_id,
        kind,
        account_id,
    )
    if challenge is None:
        raise ApiError(400 if account_id else 401, "passkey_invalid")
    return challenge


def _transports(values) -> list[AuthenticatorTransport]:
    known = {t.value for t in AuthenticatorTransport}
    return [AuthenticatorTransport(v) for v in values or [] if v in known]


async def registration_options(conn, acc: asyncpg.Record) -> dict:
    s = get_settings()
    existing = await conn.fetch(
        "select id, transports from web.webauthn_credentials where account_id = $1", acc["id"]
    )
    label = acc["email"] or acc["telegram_username"] or f"tg{acc['telegram_id']}"
    opts = generate_registration_options(
        rp_id=s.webauthn_rp_id,
        rp_name=s.webauthn_rp_name,
        user_id=acc["id"].bytes,
        user_name=label,
        user_display_name=acc["telegram_first_name"] or label,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=r["id"], transports=_transports(r["transports"]))
            for r in existing
        ],
    )
    challenge_id = await _store_challenge(conn, opts.challenge, "register", acc["id"])
    return {**options_to_json_dict(opts), "challenge_id": str(challenge_id)}


async def verify_registration(conn, account_id: UUID, challenge_id: UUID, credential) -> dict:
    """Returns the fields of a new web.webauthn_credentials row."""
    s = get_settings()
    challenge = await _take_challenge(conn, challenge_id, "register", account_id)
    try:
        v = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=s.webauthn_rp_id,
            expected_origin=s.public_origin,
        )
        transports = [t.value for t in _transports(credential["response"].get("transports"))]
    except _BAD_INPUT:
        raise ApiError(400, "passkey_invalid") from None
    return {
        "id": v.credential_id,
        "public_key": v.credential_public_key,
        "sign_count": v.sign_count,
        "transports": transports,
    }


async def authentication_options(conn) -> dict:
    # Empty allowCredentials: the browser offers discoverable passkeys, no email needed.
    opts = generate_authentication_options(
        rp_id=get_settings().webauthn_rp_id,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    challenge_id = await _store_challenge(conn, opts.challenge, "login", None)
    return {**options_to_json_dict(opts), "challenge_id": str(challenge_id)}


async def verify_authentication(conn, challenge_id: UUID, credential) -> UUID:
    """Returns the account id the passkey belongs to."""
    s = get_settings()
    challenge = await _take_challenge(conn, challenge_id, "login", None)
    try:
        parsed = parse_authentication_credential_json(credential)
        row = await conn.fetchrow(
            "select * from web.webauthn_credentials where id = $1", parsed.raw_id
        )
        if row is None or (
            parsed.response.user_handle and parsed.response.user_handle != row["account_id"].bytes
        ):
            raise ApiError(401, "passkey_invalid")
        v = verify_authentication_response(
            credential=parsed,
            expected_challenge=challenge,
            expected_rp_id=s.webauthn_rp_id,
            expected_origin=s.public_origin,
            credential_public_key=row["public_key"],
            credential_current_sign_count=row["sign_count"],
        )
    except _BAD_INPUT:
        raise ApiError(401, "passkey_invalid") from None
    await conn.execute(
        "update web.webauthn_credentials set sign_count = $2, last_used_at = now() where id = $1",
        row["id"],
        v.new_sign_count,
    )
    return row["account_id"]
