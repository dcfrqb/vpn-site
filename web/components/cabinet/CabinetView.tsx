import Devices from "@/components/cabinet/Devices";
import SubLinks from "@/components/cabinet/SubLinks";
import TrafficChart from "@/components/cabinet/TrafficChart";
import { date, gb, GB, monthName, plural, rub } from "@/lib/format";
import type { BotCabinet, CabinetPayment, CabinetSubscription } from "@/lib/types";

const BARS = 32;
const BARS_M = 20; // phones get a shorter meter so the last lit bar is never cut off
const NEAR_LIMIT = 0.85;

export const kindLabel = (kind: string) => (kind === "obhod" ? "ru-вход" : "основная");

const STATUS: Record<string, string> = { active: "активна", expired: "истекла", disabled: "отключена", limited: "лимит исчерпан", pending: "ожидает", unknown: "нет данных" };

function Bars({ count, fill, className }: { count: number; fill: number; className: string }) {
  const n = Math.min(count, Math.max(0, Math.round(fill * count)));
  return (
    <div className={className} aria-hidden="true">
      {Array.from({ length: count }, (_, j) => (
        <i key={j} className={j < n - 1 ? "f" : j === n - 1 ? "w" : undefined} />
      ))}
    </div>
  );
}

// Scale for an unlimited meter: the next round step above this month's usage.
function scale(v: number) {
  for (const s of [50, 100, 200, 500, 1000, 2000]) if (v <= s * 0.9) return s;
  return Math.ceil(v / 1000) * 1000 + 1000;
}

function Meter({ sub }: { sub: CabinetSubscription }) {
  const limit = sub.traffic?.limit_bytes ?? null;
  // A limited subscription is measured against used_bytes (it resets monthly); unlimited by this month.
  const used = limit ? (sub.traffic?.used_bytes ?? sub.traffic?.month_used_bytes ?? null) : (sub.traffic?.month_used_bytes ?? null);
  if (used == null) {
    return (
      <div className="meter">
        <div className="row">
          <span>трафик за {monthName()}</span>
          <span>нет данных</span>
        </div>
      </div>
    );
  }
  const fill = limit ? used / limit : used / GB / scale(used / GB);
  const tone = limit ? (fill >= 1 ? " full" : fill >= NEAR_LIMIT ? " near" : "") : "";
  return (
    <div className={`meter${tone}`}>
      <div className="row">
        <span>{limit ? `лимит за ${monthName()}` : `трафик за ${monthName()}`}</span>
        <span>{limit ? `${gb(used)} / ${gb(limit, 0)} гб` : `${gb(used)} гб`}</span>
      </div>
      <Bars count={BARS} fill={fill} className="bars bars-d" />
      <Bars count={BARS_M} fill={fill} className="bars bars-m" />
      {limit != null && (
        <div className="row sub-row">
          <span>{fill >= 1 ? "лимит исчерпан" : `осталось ${gb(Math.max(0, limit - used))} гб`}</span>
          <span>{sub.traffic?.reset === "month" ? "сброс 1-го числа" : ""}</span>
        </div>
      )}
    </div>
  );
}

function Screen({ sub, used }: { sub: CabinetSubscription; used: number }) {
  const active = sub.status === "active";
  const days = Math.max(0, sub.days_left ?? 0);
  const limit = sub.device_limit ?? 0;
  const lim = sub.traffic?.limit_bytes;
  const raw = (sub.plan_title || sub.plan_code || "подписка").toLowerCase();
  // The obhod title repeats the kind label ("RU-вход"); show its monthly limit instead.
  const title = raw === kindLabel(sub.kind) ? (lim ? `${gb(lim, 0)} гб в месяц` : "") : raw;
  return (
    <section className="screen cb-screen" aria-label={`Подписка: ${kindLabel(sub.kind)}`}>
      <div className="scr-top">
        <span className={active ? "on" : undefined}>
          <i className={`lamp${active ? " on" : ""}`} aria-hidden="true" />
          {kindLabel(sub.kind)} · {STATUS[sub.status] ?? sub.status}
        </span>
        <span>
          {title}
          {sub.legacy && " · архив"}
        </span>
      </div>
      <div className="cb-scr-body">
        <div>
          {sub.status === "unknown" ? (
            <div className="days dim">
              <span className="big word">--</span>
              <span className="lbl">
                панель
                <br />
                не отвечает
              </span>
            </div>
          ) : sub.is_lifetime ? (
            <div className="days">
              <span className="big word">бессрочно</span>
            </div>
          ) : (
            <div className={`days${active ? "" : " dim"}`}>
              <span className="big">{String(days).padStart(2, "0")}</span>
              <span className="lbl">
                {plural(days, "день", "дня", "дней")}
                <br />
                осталось
              </span>
            </div>
          )}
          {sub.status !== "unknown" && (
            <div className="scr-kv">
              <span>действует до</span>
              <b>{sub.is_lifetime ? "без срока" : date(sub.valid_until)}</b>
            </div>
          )}
          {sub.package && (
            <div className="scr-kv">
              <span>пакет {sub.package.limit_bytes ? `${gb(sub.package.limit_bytes, 0)} гб` : ""}</span>
              <b>{sub.package.until ? `до ${date(sub.package.until)}` : "активен"}</b>
            </div>
          )}
        </div>
        <div>
          <Meter sub={sub} />
          {limit > 0 && sub.status !== "unknown" && (
            <div className="scr-slots">
              <div className="row">
                <span>устройства</span>
                <span>
                  {used} / {limit}
                </span>
              </div>
              <div className="dots" aria-hidden="true">
                {Array.from({ length: Math.min(limit, 12) }, (_, j) => (
                  <i key={j} className={j < used ? "u" : undefined} />
                ))}
              </div>
            </div>
          )}
          {!active && sub.status !== "unknown" && (
            <a className="btn scr-btn" href="/#plans">
              продлить
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

const PAY_STATUS: Record<string, string> = { pending: "ждет оплаты", canceled: "отменен", cancelled: "отменен", refunded: "возврат", failed: "ошибка", waiting_for_capture: "ждет оплаты" };
const PAY_KIND: Record<string, string> = { obhod_package: "пакет ru-вход", promo: "промо" };

function payTitle(p: CabinetPayment) {
  if (p.description) return p.description.toLowerCase();
  const parts = [PAY_KIND[p.kind] ?? p.plan_code ?? "оплата"];
  if (p.period_months) parts.push(`${p.period_months} мес`);
  return parts.join(", ");
}

function Payments({ data }: { data: BotCabinet }) {
  const since = data.user.customer_since ?? data.stats.first_payment_at;
  return (
    <div className="panel cb-pay">
      <h4>
        оплаты <span className="mono count">{data.payments.length}</span>
      </h4>
      <div className="cb-totals">
        <div>
          <span className="caps">всего оплачено</span>
          <b className="mono">{rub(Math.round(data.stats.paid_total_rub))} ₽</b>
        </div>
        <div>
          <span className="caps">оплат</span>
          <b className="mono">{data.stats.payments_count}</b>
        </div>
        <div>
          <span className="caps">с нами с</span>
          <b className="mono">{since ? date(since) : "—"}</b>
        </div>
      </div>
      {data.payments.length === 0 && (
        <p className="note">{data.errors.includes("bot") ? "история оплат появится здесь, когда бот начнет отдавать ее сайту." : "оплат пока не было."}</p>
      )}
      <ul className="cb-list">
        {data.payments.map((p) => {
          const ok = p.status === "succeeded";
          return (
            <li key={p.id} className={ok ? undefined : "muted"}>
              <span className="mono when">{date(p.paid_at ?? p.created_at)}</span>
              <span className="what">
                {payTitle(p)}
                {!ok && <em className="chip">{PAY_STATUS[p.status] ?? p.status}</em>}
              </span>
              <b className="mono">{rub(p.amount_rub)} ₽</b>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Nodes({ data }: { data: BotCabinet }) {
  if (data.nodes.length === 0) return null;
  const online = data.nodes.filter((n) => n.online).length;
  const last = new Set(data.subscriptions.map((s) => s.last_node).filter(Boolean));
  return (
    <div className="panel cb-nodes">
      <h4>
        ноды{" "}
        <span className="mono count">
          {online} / {data.nodes.length} на связи
        </span>
      </h4>
      <div className="cb-node-grid">
        {data.nodes.map((n) => (
          <div key={n.name} className={`cb-node${n.online ? "" : " off"}`}>
            <i aria-hidden="true" />
            <span className="mono">{n.name}</span>
            <span className="st">{n.online ? (last.has(n.name) ? "ты тут" : "ок") : "нет связи"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrafficNodes({ data }: { data: BotCabinet }) {
  const rows = data.traffic_by_node.filter((r) => r.bytes_30d > 0);
  if (rows.length === 0) return null;
  const max = Math.max(...rows.map((r) => r.bytes_30d));
  return (
    <div className="cb-by-node">
      <div className="caps">по нодам, 30 дней</div>
      {rows.map((r) => (
        <div key={r.node} className="row">
          <span className="mono">{r.node}</span>
          <span className="track" aria-hidden="true">
            <i style={{ width: `${Math.max(2, (r.bytes_30d / max) * 100)}%` }} />
          </span>
          <b className="mono">{gb(r.bytes_30d)} гб</b>
        </div>
      ))}
    </div>
  );
}

export default function CabinetView({ data }: { data: BotCabinet }) {
  const subs = [...data.subscriptions].sort((a, b) => (a.kind === "main" ? -1 : b.kind === "main" ? 1 : 0));
  const hasObhod = subs.some((s) => s.kind === "obhod");
  const devicesOf = (kind: string) => data.devices.filter((d) => d.subscription === kind).length;
  const hasLinks = subs.some((s) => s.sub_url);
  const noTraffic = data.traffic_daily.every((d) => d.main_bytes + d.obhod_bytes === 0);

  return (
    <div className={`cb${hasLinks ? "" : " no-links"}`}>
      {subs.length === 0 ? (
        <div className="panel empty cb-area-screens">
          <h4>активной подписки нет</h4>
          <p className="note">в боте нет ни основной подписки, ни ru-входа. оплаты и устройства ниже, если они были.</p>
          <a className="btn solid" href="/#plans">
            выбрать тариф
          </a>
        </div>
      ) : (
        <div className={`cb-screens cb-area-screens n${subs.length}`}>
          {subs.map((s) => (
            <Screen key={s.kind} sub={s} used={devicesOf(s.kind)} />
          ))}
        </div>
      )}

      {hasLinks && (
        <div className="panel cb-area-links">
          <h4>ссылки подписки</h4>
          <SubLinks subs={subs.filter((s) => s.sub_url).map((s) => ({ kind: s.kind, label: kindLabel(s.kind), url: s.sub_url as string, limitGb: s.traffic?.limit_bytes ? Math.round(s.traffic.limit_bytes / GB) : null }))} />
        </div>
      )}

      <div className="panel cb-area-traffic">
        <h4>
          трафик{" "}
          {!(noTraffic && data.partial) && (
            <span className="mono count">
              30 {plural(30, "день", "дня", "дней")} · {gb(data.traffic_daily.reduce((a, d) => a + d.main_bytes + d.obhod_bytes, 0))} гб
            </span>
          )}
        </h4>
        {data.traffic_daily.length === 0 || (noTraffic && data.partial) ? (
          <p className="note">статистика трафика сейчас недоступна.</p>
        ) : (
          <TrafficChart days={data.traffic_daily} obhod={hasObhod} />
        )}
        <TrafficNodes data={data} />
      </div>

      <div className="panel cb-area-devices">
        <Devices devices={data.devices} labels={hasObhod} unavailable={data.partial && data.devices.length === 0} />
      </div>

      <div className="cb-area-pay">
        <Payments data={data} />
      </div>

      <div className="cb-area-nodes">
        <Nodes data={data} />
      </div>
    </div>
  );
}
