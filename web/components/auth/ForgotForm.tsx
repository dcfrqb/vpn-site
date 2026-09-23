"use client";

import { useState } from "react";
import { api } from "@/lib/client";

export default function ForgotForm({ initialEmail = "" }: { initialEmail?: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!email.trim()) return setErr("введи email.");
    setBusy(true);
    const r = await api("/api/auth/forgot", { body: { email: email.trim() } });
    setBusy(false);
    if (!r.ok) return setErr(r.message);
    setSent(true);
  };

  if (sent)
    return (
      <p className="form-ok" role="status">
        если такой email есть, мы отправили на него ссылку для сброса пароля. она действует ограниченное время. проверь папку «спам», если письма нет.
      </p>
    );

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span className="caps">email</span>
        <input className="input" type="email" name="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
      <button className="btn solid wide" type="submit" disabled={busy}>
        {busy ? "отправляем…" : "прислать ссылку"}
      </button>
    </form>
  );
}
