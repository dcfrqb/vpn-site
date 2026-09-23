"use client";

import { useState } from "react";
import { startAuthentication, type PublicKeyCredentialRequestOptionsJSON } from "@simplewebauthn/browser";
import { api, isPasskeyCancel, splitOptions } from "@/lib/client";

export default function PasskeyLogin({ next }: { next: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const go = async () => {
    setErr(null);
    if (typeof window.PublicKeyCredential === "undefined") {
      setErr("этот браузер не умеет паскеи. войди по email или через telegram.");
      return;
    }
    setBusy(true);
    const o = await api<Record<string, unknown>>("/api/auth/passkey/login/options", { method: "POST", body: {} });
    if (!o.ok) {
      setBusy(false);
      setErr(o.message);
      return;
    }
    const { challengeId, options } = splitOptions<PublicKeyCredentialRequestOptionsJSON>(o.data);
    let credential;
    try {
      credential = await startAuthentication({ optionsJSON: options });
    } catch (e) {
      setBusy(false);
      if (!isPasskeyCancel(e)) setErr("паскей не сработал. попробуй еще раз или войди другим способом.");
      return;
    }
    const v = await api("/api/auth/passkey/login/verify", { body: { challenge_id: challengeId, credential } });
    if (!v.ok) {
      setBusy(false);
      setErr(v.message);
      return;
    }
    window.location.assign(next);
  };

  return (
    <div>
      <button type="button" className="btn wide" onClick={go} disabled={busy}>
        <svg viewBox="0 0 40 40" width="22" height="22" aria-hidden="true">
          <circle cx="15" cy="13" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M3 34c1-7 6-11 12-11 3 0 5.5 1 7.5 2.5" fill="none" stroke="currentColor" strokeWidth="2" />
          <circle cx="30" cy="25" r="4" fill="#f05a24" />
          <path d="M30 29v7m0-3h3" stroke="currentColor" strokeWidth="2" fill="none" />
        </svg>
        {busy ? "ждем паскей…" : "войти по паскею"}
      </button>
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}
