"use client";

import { useRef, useState } from "react";

const NODES: [string, number][] = [
  ["nl–1", 38],
  ["nl–2", 41],
  ["fr–1", 47],
  ["fr–2", 44],
  ["us–3", 112],
  ["es–1", 61],
];
const SUB_LINK = "https://sub.example.com/k3f9x2a7q1";

export default function CabinetPreview() {
  const [toast, setToast] = useState<string | null>(null);
  const linkRef = useRef<HTMLElement>(null);

  const say = (t: string) => {
    setToast(t);
    window.setTimeout(() => setToast(null), 1800);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(SUB_LINK);
      say("ссылка скопирована");
    } catch {
      const r = document.createRange();
      if (linkRef.current) r.selectNodeContents(linkRef.current);
      const s = window.getSelection();
      s?.removeAllRanges();
      s?.addRange(r);
      say("выделено, скопируй вручную");
    }
  };

  return (
    <div className="cab">
      <div className="screen" aria-label="Пример экрана кабинета">
        <div className="scr-top">
          <span className="on">● подписка активна</span>
          <span>standard · до 28.10.2026</span>
        </div>
        <div className="days">
          <span className="big">35</span>
          <span className="lbl">
            дней
            <br />
            осталось
          </span>
        </div>
        <div className="meter">
          <div className="row">
            <span>трафик за сентябрь</span>
            <span>84.2 гб</span>
          </div>
          <div className="bars">
            {Array.from({ length: 32 }, (_, j) => (
              <i key={j} className={j < 22 ? "f" : j === 22 ? "w" : undefined} />
            ))}
          </div>
        </div>
        <div className="nodes">
          {NODES.map(([n, ms]) => (
            <div key={n} className="node">
              <span>{n}</span>
              <span className="ms">{ms} ms</span>
              <span className="st" />
            </div>
          ))}
        </div>
      </div>
      <div className="side">
        <div className="panel">
          <h4>ссылка подписки</h4>
          <div className="link-box">
            <code ref={linkRef}>{SUB_LINK}</code>
            <button type="button" onClick={copy}>
              копировать
            </button>
          </div>
          <div className="kv">
            <span>приложения</span>
            <b>happ · karing · clash mi</b>
          </div>
        </div>
        <div className="panel">
          <h4>
            устройства{" "}
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-2)" }}>
              3 / 5
            </span>
          </h4>
          <div className="slots">
            <i className="u" />
            <i className="u" />
            <i className="u" />
            <i />
            <i />
          </div>
          <div className="kv">
            <span>iphone 15</span>
            <b>сегодня</b>
          </div>
          <div className="kv">
            <span>macbook air</span>
            <b>вчера</b>
          </div>
          <div className="kv">
            <span>android tv</span>
            <b>12 дней назад</b>
          </div>
        </div>
        <div className="panel">
          <h4>оплаты</h4>
          <div className="kv">
            <span>28.09 · standard · 1 мес</span>
            <b>249 ₽</b>
          </div>
          <div className="kv">
            <span>28.08 · standard · 1 мес</span>
            <b>249 ₽</b>
          </div>
        </div>
      </div>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
