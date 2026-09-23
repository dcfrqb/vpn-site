"use client";

import { useState } from "react";
import { startRegistration, type PublicKeyCredentialCreationOptionsJSON } from "@simplewebauthn/browser";
import LogoutButton from "@/components/auth/LogoutButton";
import TelegramLogin from "@/components/auth/TelegramLogin";
import { api, checkPassword, isPasskeyCancel, PASSWORD_MIN, splitOptions } from "@/lib/client";
import { ago, date, shortAgent } from "@/lib/format";
import type { Account, SessionInfo } from "@/lib/types";

type Msg = { kind: "ok" | "err"; text: string } | null;

function Status({ msg }: { msg: Msg }) {
  if (!msg) return null;
  return (
    <p className={msg.kind === "ok" ? "form-ok" : "form-err"} role={msg.kind === "ok" ? "status" : "alert"}>
      {msg.text}
    </p>
  );
}

// Server components render the lists; after a change we reload so everything is fresh.
const reload = () => window.location.reload();

function EmailBlock({ account }: { account: Account }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    const mail = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) return setMsg({ kind: "err", text: "проверь email, в нем что-то не так." });
    if (account.has_password && !password) return setMsg({ kind: "err", text: "введи текущий пароль." });
    setBusy(true);
    const r = await api("/api/me/email", { body: account.has_password ? { email: mail, password } : { email: mail } });
    setBusy(false);
    if (!r.ok) return setMsg({ kind: "err", text: r.message });
    setMsg({ kind: "ok", text: `письмо для подтверждения ушло на ${mail}.` });
    setPassword("");
    window.setTimeout(reload, 1500);
  };

  return (
    <section className="set-block">
      <div className="set-head">
        <h3>email</h3>
        <p className="note">
          {account.email ? (
            <>
              <span className="mono">{account.email}</span> · {account.email_verified ? <span className="ok-t">подтвержден</span> : <span className="bad-t">не подтвержден</span>}
            </>
          ) : (
            "email не указан. с ним можно восстановить доступ и получать чеки."
          )}
        </p>
      </div>
      <form className="form" onSubmit={submit} noValidate>
        <label className="field">
          <span className="caps">{account.email ? "новый email" : "email"}</span>
          <input className="input" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {account.has_password && (
          <label className="field">
            <span className="caps">текущий пароль</span>
            <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
        )}
        <Status msg={msg} />
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "сохраняем…" : account.email ? "сменить email" : "добавить email"}
        </button>
      </form>
    </section>
  );
}

function PasswordBlock({ account }: { account: Account }) {
  const [current, setCurrent] = useState("");
  const [pw, setPw] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (account.has_password && !current) return setMsg({ kind: "err", text: "введи текущий пароль." });
    const bad = checkPassword(pw, repeat, account.email);
    if (bad) return setMsg({ kind: "err", text: bad });
    setBusy(true);
    const r = await api("/api/me/password", { body: account.has_password ? { current_password: current, new_password: pw } : { new_password: pw } });
    setBusy(false);
    if (!r.ok) return setMsg({ kind: "err", text: r.message });
    setCurrent("");
    setPw("");
    setRepeat("");
    setMsg({ kind: "ok", text: "пароль сохранен." });
  };

  return (
    <section className="set-block">
      <div className="set-head">
        <h3>пароль</h3>
        <p className="note">{account.has_password ? "пароль задан." : "пароля нет, входишь через telegram или паскей. можно задать, чтобы входить по email."}</p>
      </div>
      <form className="form" onSubmit={submit} noValidate>
        {account.has_password && (
          <label className="field">
            <span className="caps">текущий пароль</span>
            <input className="input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </label>
        )}
        <label className="field">
          <span className="caps">новый пароль</span>
          <input className="input" type="password" autoComplete="new-password" minLength={PASSWORD_MIN} value={pw} onChange={(e) => setPw(e.target.value)} />
          <span className="hint">не короче {PASSWORD_MIN} символов.</span>
        </label>
        <label className="field">
          <span className="caps">еще раз</span>
          <input className="input" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} />
        </label>
        <Status msg={msg} />
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "сохраняем…" : account.has_password ? "сменить пароль" : "задать пароль"}
        </button>
      </form>
    </section>
  );
}

function TelegramBlock({ account }: { account: Account }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const tg = account.telegram;

  const unlink = async () => {
    setMsg(null);
    setBusy(true);
    const r = await api("/api/me/telegram", { method: "DELETE" });
    setBusy(false);
    if (!r.ok) return setMsg({ kind: "err", text: r.message });
    reload();
  };

  return (
    <section className="set-block">
      <div className="set-head">
        <h3>telegram</h3>
        <p className="note">через telegram кабинет видит подписку из бота.</p>
      </div>
      {tg ? (
        <div className="form">
          <div className="row-item">
            <span>
              {tg.username ? <span className="mono">@{tg.username}</span> : tg.first_name || "привязан"}
              <span className="sub">id {tg.id}</span>
            </span>
            <button type="button" className="btn sm" onClick={unlink} disabled={busy}>
              отвязать
            </button>
          </div>
          <Status msg={msg} />
        </div>
      ) : (
        <TelegramLogin mode="link" onDone={reload} />
      )}
    </section>
  );
}

function PasskeysBlock({ account }: { account: Account }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const add = async () => {
    setMsg(null);
    if (typeof window.PublicKeyCredential === "undefined") return setMsg({ kind: "err", text: "этот браузер не умеет паскеи." });
    setBusy(true);
    const o = await api<Record<string, unknown>>("/api/me/passkeys/options", { method: "POST", body: {} });
    if (!o.ok) {
      setBusy(false);
      return setMsg({ kind: "err", text: o.message });
    }
    const { challengeId, options } = splitOptions<PublicKeyCredentialCreationOptionsJSON>(o.data);
    let credential;
    try {
      credential = await startRegistration({ optionsJSON: options });
    } catch (e) {
      setBusy(false);
      if (isPasskeyCancel(e)) return;
      const code = (e as { code?: string }).code;
      return setMsg({
        kind: "err",
        text: code === "ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED" ? "этот паскей уже добавлен." : "паскей не создался. попробуй еще раз.",
      });
    }
    const label = name.trim() || undefined;
    const v = await api("/api/me/passkeys/verify", { body: { challenge_id: challengeId, credential, name: label } });
    setBusy(false);
    if (!v.ok) return setMsg({ kind: "err", text: v.message });
    reload();
  };

  const remove = async (id: string) => {
    setMsg(null);
    setBusy(true);
    const r = await api(`/api/me/passkeys/${encodeURIComponent(id)}`, { method: "DELETE" });
    setBusy(false);
    if (!r.ok) return setMsg({ kind: "err", text: r.message });
    reload();
  };

  return (
    <section className="set-block">
      <div className="set-head">
        <h3>паскеи</h3>
        <p className="note">вход по face id, отпечатку или ключу без пароля.</p>
      </div>
      <div className="form">
        {account.passkeys.length === 0 && <p className="note">паскеев пока нет.</p>}
        {account.passkeys.map((p) => (
          <div key={p.id} className="row-item">
            <span>
              {p.name || "паскей"}
              <span className="sub">
                добавлен {date(p.created_at)} · вход {p.last_used_at ? ago(p.last_used_at) : "не было"}
              </span>
            </span>
            <button type="button" className="btn sm" onClick={() => remove(p.id)} disabled={busy}>
              удалить
            </button>
          </div>
        ))}
        <label className="field">
          <span className="caps">название</span>
          <input className="input" type="text" maxLength={64} placeholder="например, iphone" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <Status msg={msg} />
        <button type="button" className="btn solid" onClick={add} disabled={busy}>
          {busy ? "ждем паскей…" : "добавить паскей"}
        </button>
      </div>
    </section>
  );
}

function SessionsBlock({ sessions }: { sessions: SessionInfo[] | null }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  const revoke = async (id: string) => {
    setMsg(null);
    setBusy(true);
    const r = await api(`/api/me/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
    setBusy(false);
    if (!r.ok) return setMsg({ kind: "err", text: r.message });
    reload();
  };

  return (
    <section className="set-block">
      <div className="set-head">
        <h3>входы</h3>
        <p className="note">где сейчас открыт аккаунт. незнакомое устройство завершай сразу и смени пароль.</p>
      </div>
      <div className="form">
        {sessions === null && <p className="note">список входов сейчас недоступен.</p>}
        {sessions?.map((s) => (
          <div key={s.id} className="row-item">
            <span>
              {shortAgent(s.user_agent)}
              {s.current && <span className="here"> · это устройство</span>}
              <span className="sub">
                {s.ip ? `${s.ip} · ` : ""}активность {ago(s.last_seen_at)} · вход {date(s.created_at)}
              </span>
            </span>
            {!s.current && (
              <button type="button" className="btn sm" onClick={() => revoke(s.id)} disabled={busy}>
                завершить
              </button>
            )}
          </div>
        ))}
        <Status msg={msg} />
        <div>
          <LogoutButton everywhere className="btn" />
        </div>
      </div>
    </section>
  );
}

export default function Settings({ account, sessions }: { account: Account; sessions: SessionInfo[] | null }) {
  return (
    <div className="settings">
      <EmailBlock account={account} />
      <PasswordBlock account={account} />
      <TelegramBlock account={account} />
      <PasskeysBlock account={account} />
      <SessionsBlock sessions={sessions} />
    </div>
  );
}
