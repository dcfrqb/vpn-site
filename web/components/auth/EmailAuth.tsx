"use client";

import { useRef, useState } from "react";
import { api, checkPassword, PASSWORD_MIN } from "@/lib/client";

type Step = "email" | "login" | "register" | "no-password";

export default function EmailAuth({ next }: { next: string }) {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const pwRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setStep("email");
    setPassword("");
    setRepeat("");
    setErr(null);
  };

  const done = async (path: string, body: unknown) => {
    setBusy(true);
    const r = await api(path, { body });
    if (!r.ok) {
      setBusy(false);
      setErr(r.message);
      return;
    }
    window.location.assign(next);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const mail = email.trim();

    if (step === "email") {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) return setErr("проверь email, в нем что-то не так.");
      setBusy(true);
      const r = await api<{ exists: boolean; has_password: boolean }>("/api/auth/email/check", { body: { email: mail } });
      setBusy(false);
      if (!r.ok) return setErr(r.message);
      setStep(!r.data.exists ? "register" : r.data.has_password ? "login" : "no-password");
      window.setTimeout(() => pwRef.current?.focus(), 0);
      return;
    }

    if (step === "login") {
      if (!password) return setErr("введи пароль.");
      return done("/api/auth/login", { email: mail, password });
    }

    if (step === "register") {
      const bad = checkPassword(password, repeat, mail);
      if (bad) return setErr(bad);
      if (!consent) return setErr("без согласия на обработку данных аккаунт не создать.");
      return done("/api/auth/register", { email: mail, password });
    }
  };

  const locked = step !== "email";

  return (
    <form className="form" onSubmit={submit} noValidate>
      <div className="field">
        <span className="caps">
          <label htmlFor="auth-email">email</label>
          {locked && (
            <button type="button" className="linkish" onClick={reset}>
              изменить
            </button>
          )}
        </span>
        <input
          id="auth-email"
          className="input"
          type="email"
          name="email"
          autoComplete="username webauthn"
          inputMode="email"
          value={email}
          readOnly={locked}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>

      {step === "login" && (
        <div className="field">
          <span className="caps">
            <label htmlFor="auth-password">пароль</label>
            <a href={`/forgot?email=${encodeURIComponent(email.trim())}`}>забыл пароль</a>
          </span>
          <input ref={pwRef} id="auth-password" className="input" type="password" name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
      )}

      {step === "register" && (
        <>
          <p className="note">аккаунта с этим email еще нет. придумай пароль, и мы его создадим.</p>
          <label className="field">
            <span className="caps">новый пароль</span>
            <input ref={pwRef} className="input" type="password" name="password" autoComplete="new-password" minLength={PASSWORD_MIN} value={password} onChange={(e) => setPassword(e.target.value)} required />
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
        </>
      )}

      {step === "no-password" && (
        <p className="note">
          у этого аккаунта нет пароля. войди через telegram или паскей, либо <a href={`/forgot?email=${encodeURIComponent(email.trim())}`}>задай пароль по ссылке на почту</a>.
        </p>
      )}

      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}

      {step !== "no-password" && (
        <button className="btn solid wide" type="submit" disabled={busy || (step === "register" && !consent)}>
          {busy ? "секунду…" : step === "email" ? "продолжить" : step === "login" ? "войти" : "создать аккаунт"}
        </button>
      )}
    </form>
  );
}
