"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/client";
import { safeNext } from "@/lib/next-path";

// Only the sign-in API is used. No access to Gmail, Drive or other Google data.
type Identity = {
  initialize: (options: { client_id: string; nonce: string; auto_select: boolean; callback: (response: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: { type: string; theme: string; size: string; text: string; locale: string }) => void;
};
declare global { interface Window { google?: { accounts: { id: Identity } } } }

export default function GoogleLogin({ next = "/cabinet", linking = false }: { next?: string; linking?: boolean }) {
  const button = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);

  useEffect(() => {
    let active = true;
    api<{ enabled: boolean }>("/api/auth/google/config").then((r) => {
      if (active) setEnabled(r.ok && r.data.enabled);
    });
    return () => { active = false; };
  }, []);

  const prepare = useCallback(async () => {
    const google = window.google?.accounts.id;
    if (!google || !button.current) return;
    setErr(null);
    const r = await api<{ client_id: string; nonce: string }>("/api/auth/google/options", { body: {} });
    if (!r.ok) { setErr(r.message); return; }
    google.initialize({
      client_id: r.data.client_id,
      nonce: r.data.nonce,
      auto_select: false,
      callback: async ({ credential }) => {
        if (pending.current) return;
        pending.current = true;
        setBusy(true);
        setErr(null);
        const result = await api("/api/auth/google", { body: { credential } });
        pending.current = false;
        setBusy(false);
        if (!result.ok) { setErr(result.message); return; }
        if (linking) window.location.reload();
        else window.location.assign(safeNext(next));
      },
    });
    button.current.replaceChildren();
    google.renderButton(button.current, { type: "standard", theme: "outline", size: "large", text: "continue_with", locale: "ru" });
  }, [next, linking]);

  if (enabled === null) return linking ? null : <section id="google-login" className="method">
    <h3 className="caps">google</h3><p className="note" role="status">проверяем доступность входа…</p>
  </section>;
  if (!enabled) return linking ? null : <section id="google-login" className="method">
    <h3 className="caps">google</h3>
    <p className="note">вход через google временно недоступен. используй email или другой способ.</p>
  </section>;
  return (
    <section id="google-login" className={linking ? "set-block" : "method"}>
      {linking ? <div className="set-head"><h3>google</h3><p className="note">вход без отдельного пароля сайта.</p></div> : <h3 className="caps">google</h3>}
      <div className="form">
        <Script src="https://accounts.google.com/gsi/client?hl=ru" onReady={() => { void prepare(); }} onError={() => setErr("Google не загрузился. Проверь соединение или используй другой способ входа.")} />
        <div ref={button} hidden={busy || !!err} />
        {busy && <p className="note" role="status">проверяем вход…</p>}
        {err && <>
          <p className="form-err" role="alert">{err}</p>
          <button className="btn" type="button" onClick={() => window.google ? prepare() : window.location.reload()}>попробовать снова</button>
        </>}
        <p className="note">{linking ? "Google станет еще одним способом входа в этот аккаунт." : "при первом входе создадим аккаунт. пароль Google остается у Google."}</p>
      </div>
    </section>
  );
}
