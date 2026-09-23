"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/client";
import type { Account } from "@/lib/types";

type Props = {
  mode: "login" | "link";
  next?: string;
  onDone?: (account: Account) => void;
};

type Start = { request_id: string; link: string; expires_in: number };
type Status = { status: "pending" | "expired" | "denied" } | { status: "ok"; account: Account };

const POLL_MS = 2000;
// Re-create the request a bit before the api's 5 minute expiry so the link is always fresh.
const REFRESH_MS = 4 * 60 * 1000;

// Sign-in / linking through the Telegram app: the link opens @crs_vpn_bot with a one-time
// payload, the user confirms there, this tab polls the api until the request is confirmed.
export default function TelegramLogin({ mode, next = "/cabinet", onDone }: Props) {
  const [req, setReq] = useState<Start | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const latest = useRef({ mode, next, onDone });
  latest.current = { mode, next, onDone };
  const waitingRef = useRef(false);
  waitingRef.current = waiting;

  const create = useCallback(async () => {
    const r = await api<Start>("/api/auth/tg/start", { body: { mode } });
    if (!r.ok) {
      setReq(null);
      setErr(r.status === 503 ? "вход через telegram временно недоступен. войди по email или паскею." : r.message);
      return;
    }
    setErr(null);
    setReq(r.data);
  }, [mode]);

  useEffect(() => {
    create();
    const t = window.setInterval(() => {
      // never swap the request while the user is confirming it in telegram
      if (!document.hidden && !waitingRef.current) create();
    }, REFRESH_MS);
    return () => window.clearInterval(t);
  }, [create]);

  useEffect(() => {
    if (!waiting || !req) return;
    let stop = false;

    const poll = async () => {
      if (stop) return;
      const r = await api<Status>(`/api/auth/tg/status?id=${req.request_id}`, { method: "GET" });
      if (stop) return;
      if (!r.ok) {
        if (r.status === 404) {
          setWaiting(false);
          setNote("запрос не найден. нажми кнопку еще раз.");
          create();
        }
        return;
      }
      const s = r.data;
      if (s.status === "ok") {
        stop = true;
        const { mode: m, next: to, onDone: cb } = latest.current;
        if (m === "login") {
          window.location.assign(to);
        } else {
          setWaiting(false);
          setNote("telegram привязан.");
          cb?.(s.account);
        }
      } else if (s.status === "denied") {
        stop = true;
        setWaiting(false);
        setNote("вход отменен в telegram.");
        create();
      } else if (s.status === "expired") {
        stop = true;
        setWaiting(false);
        setNote("ссылка устарела. нажми кнопку еще раз.");
        create();
      }
    };

    const t = window.setInterval(poll, POLL_MS);
    const onVisible = () => {
      if (!document.hidden) poll();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stop = true;
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [waiting, req, create]);

  const label = mode === "login" ? "войти через telegram" : "привязать telegram";

  return (
    <div className="tg">
      {req ? (
        <a
          className="btn solid wide"
          href={req.link}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => {
            setNote(null);
            setWaiting(true);
          }}
        >
          {label}
        </a>
      ) : (
        <button className="btn solid wide" type="button" disabled>
          {err ? label : "готовим ссылку…"}
        </button>
      )}
      {waiting && <p className="note">подтверди вход в telegram и вернись сюда. страница обновится сама.</p>}
      {note && <p className="note">{note}</p>}
      {err && (
        <p className="form-err" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}
