"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/client";
import { paymentUrl, type Order } from "./Checkout";

const LABELS: Record<string, [string, string]> = {
  creating: ["готовим оплату", "заказ сохранен. проверяем ответ платежного сервиса."],
  pending: ["ожидаем оплату", "если ты уже оплатил, подожди немного: подтверждение может прийти не сразу."],
  paid: ["оплата получена", "готовим подключение. не нужно платить повторно."],
  provisioning: ["готовим подключение", "оплата получена. ссылка VPN скоро появится в кабинете, повторная оплата не нужна."],
  fulfilled: ["подписка готова", "ссылка подключения, срок и устройства доступны в кабинете."],
  canceled: ["оплата отменена", "этот заказ не оплачен. можно выбрать тариф и попробовать снова."],
  failed: ["заказ не создан", "выбери тариф заново. если деньги списались, обратись в поддержку с номером заказа."],
  held: ["нужна проверка", "не оплачивай повторно. обратись в поддержку и укажи номер заказа ниже."],
  refunding: ["возврат обрабатывается", "проверяем возврат и обновляем срок подписки."],
  refunded: ["платеж возвращен", "срок подписки скорректирован с учетом возврата."],
};
const TERMINAL = new Set(["fulfilled", "canceled", "failed", "held", "refunded"]);

export default function OrderStatus({ id }: { id: string }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    setBusy(true);
    const r = await api<Order>(`/api/checkout/orders/${encodeURIComponent(id)}`);
    setBusy(false);
    if (!r.ok) {
      if (r.status === 401) window.location.assign(`/login?next=${encodeURIComponent(`/checkout/${id}`)}`);
      setError(r.message);
    } else { setOrder(r.data); setError(null); }
  }, [id]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (order && TERMINAL.has(order.state)) return;
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 10000);
    return () => window.clearInterval(timer);
  }, [order, refresh]);
  const [title, detail] = LABELS[order?.state ?? "creating"] ?? ["проверяем заказ", "обнови статус через несколько секунд."];
  const url = paymentUrl(order?.confirmation_url ?? null);
  return <section className="form" aria-live="polite">
    <div className="set-head"><h3>{title}</h3><p className="note">{detail}</p></div>
    {order && <p className="mono">{order.title} · {order.months} мес · {order.amount_rub.toLocaleString("ru-RU")} ₽</p>}
    {error && <p className="form-err" role="alert">{error}</p>}
    {order?.state === "pending" && url && <a className="btn solid" href={url}>продолжить оплату</a>}
    {order?.state === "fulfilled" && <a className="btn solid" href="/cabinet">открыть кабинет</a>}
    {order && ["canceled", "failed"].includes(order.state) && <a className="btn" href={`/checkout?plan=${encodeURIComponent(order.plan_code)}&months=${order.months}`}>новый заказ</a>}
    {(!order || !TERMINAL.has(order.state)) && <button className="btn" type="button" disabled={busy} onClick={() => { void refresh(); }}>{busy ? "проверяем…" : "обновить статус"}</button>}
    <p className="note">номер заказа: <span className="mono" style={{ overflowWrap: "anywhere" }}>{id}</span></p>
    <a className="note" href="/cabinet">в кабинет</a>
  </section>;
}
