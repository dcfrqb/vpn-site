"use client";

import { useState } from "react";
import { api } from "@/lib/client";

export default function LogoutButton({ everywhere = false, className = "linkish" }: { everywhere?: boolean; className?: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const go = async () => {
    setBusy(true);
    setErr(null);
    const r = await api(everywhere ? "/api/auth/logout-all" : "/api/auth/logout", { method: "POST" });
    // 401 means the session is already gone: that is still a successful exit.
    if (r.ok || r.status === 401) {
      window.location.assign("/login");
      return;
    }
    setBusy(false);
    setErr(r.message);
  };

  return (
    <>
      <button type="button" className={className} onClick={go} disabled={busy}>
        {everywhere ? "выйти везде" : "выйти"}
      </button>
      {err && (
        <span className="form-err" role="alert">
          {err}
        </span>
      )}
    </>
  );
}
