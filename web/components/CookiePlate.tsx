"use client";

import { useEffect, useState } from "react";
const KEY = "crs-cookie";

export default function CookiePlate() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    try { if (!localStorage.getItem(KEY)) setVisible(true); }
    catch { setVisible(true); }
  }, []);
  const done = () => {
    try { localStorage.setItem(KEY, "necessary"); } catch { /* This page only. */ }
    setVisible(false);
  };
  if (!visible) return null;
  return <aside className="cookie" aria-label="Служебные cookie">
    <div className="hd"><span><i /> cookie</span><span>01 / 01</span></div>
    <p>используем служебные cookie для входа и защиты запросов. рекламной аналитики на сайте нет. <a href="/legal/cookies">что сохраняется</a></p>
    <div className="row"><button type="button" className="solid" onClick={done}>понятно</button></div>
  </aside>;
}
