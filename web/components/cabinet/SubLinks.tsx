"use client";

import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";

type Item = { kind: string; label: string; url: string; limitGb: number | null };

// "https://sub.example.com/abcdef123" → "sub.example.com/abcd••••••••"
function mask(url: string) {
  try {
    const u = new URL(url);
    const tail = (u.pathname + u.search).replace(/^\//, "");
    return `${u.host}/${tail.slice(0, 4)}${"•".repeat(10)}`;
  } catch {
    return "•".repeat(24);
  }
}

function Qr({ url, label }: { url: string; label: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    QRCode.toString(url, { type: "svg", margin: 1, errorCorrectionLevel: "M", color: { dark: "#0f0e12ff", light: "#ffffffff" } })
      .then((s) => alive && setSvg(s))
      .catch(() => alive && setSvg(""));
    return () => {
      alive = false;
    };
  }, [url]);
  if (svg === "") return <p className="form-err">не получилось нарисовать qr. скопируй ссылку.</p>;
  return (
    <div className="cb-qr" role="img" aria-label={`qr-код ссылки: ${label}`}>
      {svg ? <div dangerouslySetInnerHTML={{ __html: svg }} /> : <div className="ph" />}
      <p className="note">открой приложение, нажми «добавить» и отсканируй код камерой.</p>
    </div>
  );
}

function Link({ item }: { item: Item }) {
  const [shown, setShown] = useState(false);
  const [qr, setQr] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const ref = useRef<HTMLElement>(null);

  const say = (t: string) => {
    setToast(t);
    window.setTimeout(() => setToast(null), 1800);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(item.url);
      say("ссылка скопирована");
    } catch {
      // Clipboard API blocked: reveal and select the text for a manual copy.
      setShown(true);
      window.setTimeout(() => {
        const r = document.createRange();
        if (ref.current) r.selectNodeContents(ref.current);
        const s = window.getSelection();
        s?.removeAllRanges();
        s?.addRange(r);
      }, 0);
      say("выделено, скопируй вручную");
    }
  };

  return (
    <div className="cb-link">
      <div className="cb-link-head">
        <span className="caps">{item.label}</span>
        {item.kind === "obhod" && <span className="note">{item.limitGb ? `отдельная подписка, ${item.limitGb} гб в месяц` : "отдельная подписка"}</span>}
      </div>
      <div className="link-box">
        <code ref={ref} className={shown ? undefined : "masked"}>
          {shown ? item.url : mask(item.url)}
        </code>
        <button type="button" className="ghost" onClick={() => setShown((v) => !v)} aria-pressed={shown}>
          {shown ? "скрыть" : "показать"}
        </button>
        <button type="button" onClick={copy}>
          копировать
        </button>
      </div>
      <button type="button" className="linkish cb-qr-t" onClick={() => setQr((v) => !v)} aria-expanded={qr}>
        {qr ? "спрятать qr" : "показать qr-код"}
      </button>
      {qr && <Qr url={item.url} label={item.label} />}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}

export default function SubLinks({ subs }: { subs: Item[] }) {
  return (
    <>
      {subs.map((s) => (
        <Link key={s.kind} item={s} />
      ))}
      <div className="kv cb-apps">
        <span>приложения</span>
        <b>happ · karing · clash mi</b>
      </div>
      <p className="note cb-hint">
        ссылка личная, не пересылай ее. в приложении: «добавить подписку» → вставь ссылку или отсканируй qr.
        {subs.length > 1 && " ru-вход добавь в приложение второй подпиской."}
      </p>
    </>
  );
}
