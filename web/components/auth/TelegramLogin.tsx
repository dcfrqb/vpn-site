"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/client";
import { TG_BOT as BOT } from "@/lib/config";
import type { Account } from "@/lib/types";


type TgUser = { id: number; first_name: string; last_name?: string; username?: string; photo_url?: string; auth_date: number; hash: string };

declare global {
  interface Window {
    __crsTgAuth?: (user: TgUser) => void;
  }
}

type Props = {
  mode: "login" | "link";
  next?: string;
  onDone?: (account: Account) => void;
};

export default function TelegramLogin({ mode, next = "/cabinet", onDone }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const latest = useRef({ mode, next, onDone });
  latest.current = { mode, next, onDone };

  useEffect(() => {
    window.__crsTgAuth = async (user: TgUser) => {
      setBusy(true);
      setErr(null);
      const r = await api<{ account: Account }>("/api/auth/telegram", { body: user });
      if (!r.ok) {
        setBusy(false);
        setErr(r.message);
        return;
      }
      const { mode: m, next: to, onDone: cb } = latest.current;
      if (m === "login") {
        window.location.assign(to);
      } else {
        setBusy(false);
        cb?.(r.data.account);
      }
    };

    const el = box.current;
    if (!el) return;
    el.innerHTML = "";
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://telegram.org/js/telegram-widget.js?22";
    s.setAttribute("data-telegram-login", BOT);
    s.setAttribute("data-size", "large");
    s.setAttribute("data-radius", "20");
    s.setAttribute("data-userpic", "false");
    s.setAttribute("data-lang", "ru");
    s.setAttribute("data-onauth", "window.__crsTgAuth(user)");
    s.onerror = () => setFailed(true);
    el.appendChild(s);

    // The script can load and still render nothing (blocked iframe, wrong domain): check later.
    const t = window.setTimeout(() => {
      if (!el.querySelector("iframe")) setFailed(true);
    }, 8000);

    return () => {
      window.clearTimeout(t);
      delete window.__crsTgAuth;
    };
  }, []);

  return (
    <div className="tg">
      <div ref={box} className="tg-box" aria-busy={busy} />
      {failed && <p className="note">виджет telegram не загрузился. возможно, telegram у тебя заблокирован. войди по email или паскею, telegram можно привязать позже.</p>}
      {busy && <p className="note">проверяем данные telegram…</p>}
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}
