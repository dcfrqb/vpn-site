"use client";

import { useState } from "react";
import { api } from "@/lib/client";
import { agoFine } from "@/lib/format";
import type { CabinetDevice } from "@/lib/types";

const VISIBLE = 5;

const known = (d: CabinetDevice) => !!(d.model || d.platform);

// Model first ("iPhone16,2"), the platform when there is no model.
function name(d: CabinetDevice) {
  if (!known(d)) return "неизвестное устройство";
  return d.model && d.model !== d.platform ? d.model : (d.platform || "").toLowerCase();
}

// Second line: platform + os version + app ("ios 19.0 · happ/3.1.0"); an unknown device shows its hwid.
function meta(d: CabinetDevice) {
  if (!known(d)) return `hwid: ${d.hwid}`;
  const os = [(d.platform || "").toLowerCase(), d.os_version].filter(Boolean).join(" ");
  return [os, d.app?.toLowerCase()].filter(Boolean).join(" · ");
}

const seen = (d: CabinetDevice) => (d.last_seen_at ? new Date(d.last_seen_at).getTime() || 0 : 0);

export default function Devices({ devices, labels, unavailable = false }: { devices: CabinetDevice[]; labels: boolean; unavailable?: boolean }) {
  const [list, setList] = useState(() => [...devices].sort((a, b) => seen(b) - seen(a)));
  const [all, setAll] = useState(false);
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
        {(all ? list : list.slice(0, VISIBLE)).map((d) => (
          <li key={d.hwid}>
            <span className="what" title={known(d) ? `hwid: ${d.hwid}` : undefined}>
              <span className={known(d) ? "nm" : "nm unknown"}>{name(d)}</span>
              {labels && d.subscription === "obhod" && <em className="chip">ru-вход</em>}
              <span className={known(d) ? "sub" : "sub hwid"}>{meta(d) || " "}</span>
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
      {list.length > VISIBLE && (
        <button type="button" className="linkish cb-more" onClick={() => setAll((v) => !v)} aria-expanded={all}>
          {all ? "свернуть" : `показать еще ${list.length - VISIBLE}`}
        </button>
      )}
      {asking && <p className="note">слот освободится. если приложение на этом устройстве подключится снова, оно займет слот заново.</p>}
      {err && <p className="form-err">{err}</p>}
    </>
  );
}
