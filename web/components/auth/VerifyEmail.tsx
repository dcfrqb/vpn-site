"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/client";

export default function VerifyEmail({ token }: { token: string }) {
  const [state, setState] = useState<"wait" | "ok" | "bad">("wait");
  const [msg, setMsg] = useState("");
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return; // strict mode runs effects twice; the token is single-use
    sent.current = true;
    api("/api/auth/verify-email", { body: { token } }).then((r) => {
      if (r.ok) setState("ok");
      else {
        setState("bad");
        setMsg(r.message);
      }
    });
  }, [token]);

  if (state === "wait") return <p className="note">проверяем ссылку…</p>;
  if (state === "ok")
    return (
      <div className="form">
        <p className="form-ok" role="status">
          email подтвержден.
        </p>
        <a className="btn solid wide" href="/cabinet">
          в кабинет
        </a>
      </div>
    );
  return (
    <div className="form">
      <p className="form-err" role="alert">
        {msg || "ссылка не подошла."} запроси новое письмо в настройках кабинета.
      </p>
      <a className="btn wide" href="/cabinet/settings">
        в настройки
      </a>
    </div>
  );
}
