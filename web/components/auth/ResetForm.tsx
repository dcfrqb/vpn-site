"use client";

import { useState } from "react";
import { api, checkPassword, PASSWORD_MIN } from "@/lib/client";

export default function ResetForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const bad = checkPassword(password, repeat);
    if (bad) return setErr(bad);
    setBusy(true);
    const r = await api("/api/auth/reset", { body: { token, password } });
    setBusy(false);
    if (!r.ok) return setErr(r.message);
    setDone(true);
  };

  if (done)
    return (
      <div className="form">
        <p className="form-ok" role="status">
          пароль изменен. все старые входы завершены, войди заново с новым паролем.
        </p>
        <a className="btn solid wide" href="/login">
          войти
        </a>
      </div>
    );

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span className="caps">новый пароль</span>
        <input className="input" type="password" autoComplete="new-password" minLength={PASSWORD_MIN} value={password} onChange={(e) => setPassword(e.target.value)} required />
        <span className="hint">не короче {PASSWORD_MIN} символов.</span>
      </label>
      <label className="field">
        <span className="caps">еще раз</span>
        <input className="input" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
      </label>
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
      <button className="btn solid wide" type="submit" disabled={busy}>
        {busy ? "сохраняем…" : "сохранить пароль"}
      </button>
    </form>
  );
}
