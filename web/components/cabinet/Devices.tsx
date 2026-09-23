"use client";

import { useState } from "react";
import { api } from "@/lib/client";
import { agoFine } from "@/lib/format";
import type { CabinetDevice } from "@/lib/types";

function name(d: CabinetDevice) {
  const p = (d.platform || "").toLowerCase();
  const model = d.model && d.model !== d.platform ? d.model : "";
  return [p || "устройство", model].filter(Boolean).join(" · ");
}

function meta(d: CabinetDevice) {
  return [d.os_version && `${(d.platform || "").toLowerCase()} ${d.os_version}`.trim(), d.app?.toLowerCase()].filter(Boolean).join(" · ");
}

export default function Devices({ devices, labels, unavailable = false }: { devices: CabinetDevice[]; labels: boolean; unavailable?: boolean }) {
  const [list, setList] = useState(devices);
  const [asking, setAsking] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const remove = async (d: CabinetDevice) => {
    setBusy(true);
    setErr(null);
    const before = list;
    setList((l) => l.filter((x) => x.hwid !== d.hwid)); // optimistic
    setAsking(null);
    const r = await api(`/api/cabinet/devices/${encodeURIComponent(d.hwid)}`, { method: "DELETE" });
    setBusy(false);
    if (r.ok || r.status === 404) {
      // 404: the device is already gone in the bot, the list is right as it is.
      return;
    }
    setList(before);
    setErr(r.status === 503 ? "бот не отвечает. попробуй через минуту." : r.message.toLowerCase());
  };

  return (
    <>
      <h4>
        устройства <span className="mono count">{list.length}</span>
      </h4>
      {list.length === 0 && <p className="note">{unavailable ? "список устройств сейчас недоступен." : "пока ни одно устройство не подключалось."}</p>}
      <ul className="cb-list cb-dev">
        {list.map((d) => (
          <li key={d.hwid}>
            <span className="what">
              {name(d)}
              {labels && d.subscription === "obhod" && <em className="chip">ru-вход</em>}
              <span className="sub">{meta(d) || " "}</span>
            </span>
            {asking === d.hwid ? (
              <span className="cb-ask">
                <span className="q">удалить?</span>
                <button type="button" className="btn sm danger" disabled={busy} onClick={() => remove(d)}>
                  да
                </button>
                <button type="button" className="btn sm" onClick={() => setAsking(null)}>
                  нет
                </button>
              </span>
            ) : (
              <span className="cb-dev-r">
                <b className="mono" suppressHydrationWarning>
                  {agoFine(d.last_seen_at)}
                </b>
                <button type="button" className="linkish del" disabled={busy} onClick={() => setAsking(d.hwid)}>
                  удалить
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {asking && <p className="note">слот освободится. если приложение на этом устройстве подключится снова, оно займет слот заново.</p>}
      {err && <p className="form-err">{err}</p>}
    </>
  );
}
