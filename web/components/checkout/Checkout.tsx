"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/client";

type Quote = { plan_code: string; title: string; months: number; amount_rub: number; currency: string; enabled: boolean };
export type Order = { id: string; state: string; plan_code: string; title: string; months: number; amount_rub: number; currency: string; confirmation_url: string | null };

export function paymentUrl(raw: string | null) {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    // The standalone local demo uses a fake bank; this branch is removed in production.
    const demoOrigin = process.env.NEXT_PUBLIC_CHECKOUT_DEMO_ORIGIN;
    if (process.env.NODE_ENV === "development" && demoOrigin && url.origin === demoOrigin &&
      url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname)) return url.href;
    return url.protocol === "https:" && ["yookassa.ru", "yoomoney.ru"].includes(url.hostname) ? url.href : null;
  } catch { return null; }
}

export default function Checkout({ plan, months, accountId }: { plan: string; months: number; accountId: string }) {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [existing, setExisting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const path = `/checkout?plan=${encodeURIComponent(plan)}&months=${months}`;

  useEffect(() => {
    let stopped = false;
    api<Quote>("/api/checkout/quote", { body: { plan_code: plan, months } }).then((r) => {
      if (stopped) return;
      if (!r.ok) {
        if (r.status === 401) window.location.assign(`/login?next=${encodeURIComponent(path)}`);
        setError(r.message);
      } else setQuote(r.data);
    });
    return () => { stopped = true; };
  }, [plan, months, path]);

  const pay = async () => {
    if (!quote || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    setExisting(null);
    const storageKey = `crs.checkout.${accountId}.${plan}.${months}`;
    let id = crypto.randomUUID();
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved && /^[0-9a-f-]{36}$/i.test(saved)) id = saved as typeof id;
      sessionStorage.setItem(storageKey, id);
    } catch { /* The server also reuses pending orders when browser storage is unavailable. */ }
    const result = await api<Order>("/api/checkout/orders", {
      body: { order_id: id, plan_code: plan, months, expected_amount_rub: quote.amount_rub },
    });
    pending.current = false;
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      if (result.order_id) setExisting(result.order_id);
      return;
    }
    try { sessionStorage.removeItem(storageKey); } catch { /* Optional cache. */ }
    const url = paymentUrl(result.data.confirmation_url);
    if (result.data.state === "pending" && url) window.location.assign(url);
    else window.location.assign(`/checkout/${encodeURIComponent(result.data.id)}`);
  };

  return (
    <section className="form" aria-label="Подтверждение заказа">
      {quote ? <>
        <div className="set-head"><h3>{quote.title}</h3><p className="note">{quote.months} мес · разовая оплата, без автосписаний</p></div>
        <p className="mono" style={{ fontSize: "clamp(30px, 5vw, 48px)", margin: 0 }}>{quote.amount_rub.toLocaleString("ru-RU")} ₽</p>
        <p className="note">после оплаты подписка появится в кабинете. данные карты вводятся на странице ЮKassa.</p>
        <button className="btn solid" type="button" disabled={busy || !quote.enabled} onClick={pay}>{busy ? "создаем заказ…" : "перейти к оплате"}</button>
        {!quote.enabled && <p className="note">прием платежей пока не включен.</p>}
      </> : !error && <p className="note" role="status">проверяем тариф и сумму…</p>}
      {error && <p className="form-err" role="alert">{error}</p>}
      {existing && <a className="btn" href={`/checkout/${encodeURIComponent(existing)}`}>открыть незавершенный заказ</a>}
      <a className="note" href="/#plans">выбрать другой тариф или срок</a>
    </section>
  );
}
