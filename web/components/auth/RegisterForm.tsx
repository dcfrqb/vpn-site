"use client";

import { useState } from "react";
import { api, checkPassword, PASSWORD_MIN } from "@/lib/client";

export default function RegisterForm({ next }: { next: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const mail = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) return setErr("проверь email, в нем что-то не так.");
    const bad = checkPassword(password, repeat, mail);
    if (bad) return setErr(bad);
    if (!consent) return setErr("без согласия на обработку данных аккаунт не создать.");
    setBusy(true);
    const r = await api("/api/auth/register", { body: { email: mail, password } });
    if (!r.ok) {
      setBusy(false);
      setErr(r.message);
      return;
    }
    window.location.assign(next);
  };

  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span className="caps">email</span>
        <input className="input" type="email" name="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="field">
        <span className="caps">пароль</span>
        <input className="input" type="password" name="password" autoComplete="new-password" minLength={PASSWORD_MIN} value={password} onChange={(e) => setPassword(e.target.value)} required />
        <span className="hint">не короче {PASSWORD_MIN} символов. проще всего взять несколько слов подряд.</span>
      </label>
      <label className="field">
        <span className="caps">пароль еще раз</span>
        <input className="input" type="password" name="repeat" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
      </label>
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} required />
        <span>
          даю <a href="/legal/cookies">согласие на обработку персональных данных</a>
        </span>
      </label>
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
      <button className="btn solid wide" type="submit" disabled={busy || !consent}>
        {busy ? "создаем…" : "создать аккаунт"}
      </button>
    </form>
  );
}
