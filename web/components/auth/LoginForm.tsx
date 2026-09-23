"use client";

import { useState } from "react";
import { api } from "@/lib/client";

export default function LoginForm({ next }: { next: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!email.trim() || !password) {
      setErr("введи email и пароль.");
      return;
    }
    setBusy(true);
    const r = await api("/api/auth/login", { body: { email: email.trim(), password } });
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
        <input className="input" type="email" name="email" autoComplete="username webauthn" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <div className="field">
        <span className="caps">
          <label htmlFor="login-password">пароль</label>
          <a href="/forgot">забыл пароль</a>
        </span>
        <input id="login-password" className="input" type="password" name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </div>
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
      <button className="btn solid wide" type="submit" disabled={busy}>
        {busy ? "входим…" : "войти"}
      </button>
    </form>
  );
}
