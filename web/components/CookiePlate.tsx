"use client";

import { useEffect, useState } from "react";

const KEY = "crs-cookie";

export default function CookiePlate() {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [analytics, setAnalytics] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(KEY)) setVisible(true);
    } catch {
      setVisible(true);
    }
  }, []);

  const done = (value: "all" | "none") => {
    try {
      localStorage.setItem(KEY, value);
    } catch {
      /* storage blocked: choice lives for this page only */
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <aside className="cookie" aria-label="Настройки cookie">
      <div className="hd">
        <span>
          <i />
          cookie
        </span>
        <span>01 / 01</span>
      </div>
      <p>
        необходимые cookie нужны для входа и оплаты. аналитику включаем только с твоего согласия. <a href="/legal/cookies">подробнее</a>
      </p>
      {open && (
        <div className="opts">
          <label>
            необходимые <input type="checkbox" checked disabled />
          </label>
          <label>
            аналитика <input type="checkbox" checked={analytics} onChange={(e) => setAnalytics(e.target.checked)} />
          </label>
        </div>
      )}
      <div className="row">
        <button type="button" onClick={() => done("none")}>
          только необходимые
        </button>
        <button type="button" className="solid" onClick={() => done("all")}>
          принять все
        </button>
      </div>
      <div className="row">
        <button
          type="button"
          style={{ flex: "none", border: 0, padding: "4px 0", color: "#8c8b92", fontSize: 12 }}
          onClick={() => (open ? done(analytics ? "all" : "none") : setOpen(true))}
        >
          {open ? "сохранить выбор" : "настроить"}
        </button>
      </div>
    </aside>
  );
}
