import CopyLink from "@/components/cabinet/CopyLink";
import { ago, date, dayMonth, monthName, plural, rub } from "@/lib/format";
import type { CabinetData } from "@/lib/types";

const BARS = 32;
const BARS_M = 20; // phones get a shorter meter so the last lit bar is never cut off

function Bars({ count, fill, className }: { count: number; fill: number; className: string }) {
  const n = Math.min(count, Math.round(fill * count));
  return (
    <div className={className} aria-hidden="true">
      {Array.from({ length: count }, (_, j) => (
        <i key={j} className={j < n - 1 ? "f" : j === n - 1 ? "w" : undefined} />
      ))}
    </div>
  );
}
const OK_PAY = new Set(["succeeded", "paid", "ok", "success", "completed"]);
const PAY_STATUS: Record<string, string> = { pending: "ждет оплаты", canceled: "отменен", cancelled: "отменен", refunded: "возврат", failed: "ошибка" };

// Scale for the traffic meter: the next round step above this month's usage.
function scale(gb: number) {
  for (const s of [50, 100, 200, 500, 1000, 2000]) if (gb <= s * 0.9) return s;
  return Math.ceil(gb / 1000) * 1000 + 1000;
}

export default function CabinetView({ data }: { data: CabinetData }) {
  const sub = data.subscription;
  const active = sub?.status === "active";
  const days = sub ? Math.max(0, sub.days_left) : 0;
  const gb = sub?.traffic_month_gb ?? 0;
  const used = data.devices.length;
  const limit = sub?.device_limit ?? 0;

  return (
    <div className="cab">
      <div className="screen" aria-label="Экран подписки">
        <div className="scr-top">
          <span className={active ? "on" : undefined}>{active ? "● подписка активна" : sub ? "○ подписка не активна" : "○ подписки нет"}</span>
          {sub && (
            <span>
              {sub.plan} · до {date(sub.valid_until)}
            </span>
          )}
        </div>
        <div className="days">
          <span className="big">{String(days).padStart(2, "0")}</span>
          <span className="lbl">
            {plural(days, "день", "дня", "дней")}
            <br />
            осталось
          </span>
        </div>
        <div className="meter">
          <div className="row">
            <span>трафик за {monthName()}</span>
            <span>{gb.toFixed(1)} гб</span>
          </div>
          <Bars count={BARS} fill={gb / scale(gb)} className="bars bars-d" />
          <Bars count={BARS_M} fill={gb / scale(gb)} className="bars bars-m" />
        </div>
        {data.nodes.length > 0 && (
          <div className="nodes">
            {data.nodes.map((n) => (
              <div key={n.name} className="node">
                <span>{n.name}</span>
                <span className="ms">{n.online && n.ping_ms != null ? `${n.ping_ms} ms` : "нет связи"}</span>
                <span className={`st${n.online ? "" : " off"}`} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="side">
        <div className="panel">
          <h4>ссылка подписки</h4>
          {sub?.sub_url ? (
            <>
              <CopyLink url={sub.sub_url} />
              <div className="kv">
                <span>приложения</span>
                <b>happ · karing · clash mi</b>
              </div>
            </>
          ) : (
            <>
              <p className="note">ссылка появится после оплаты.</p>
              <a className="btn solid" href="/#plans">
                выбрать тариф
              </a>
            </>
          )}
        </div>

        {sub && (
          <div className="panel">
            <h4>
              устройства{" "}
              <span className="mono count">
                {used} / {limit}
              </span>
            </h4>
            {limit > 0 && (
              <div className="slots">
                {Array.from({ length: Math.min(limit, 12) }, (_, j) => (
                  <i key={j} className={j < used ? "u" : undefined} />
                ))}
              </div>
            )}
            {data.devices.length === 0 && <p className="note">пока ни одно устройство не подключалось.</p>}
            {data.devices.map((d, j) => (
              <div key={`${d.name}-${j}`} className="kv">
                <span>{d.name}</span>
                <b>{ago(d.last_seen_at)}</b>
              </div>
            ))}
          </div>
        )}

        <div className="panel">
          <h4>оплаты</h4>
          {data.payments.length === 0 && <p className="note">оплат пока не было.</p>}
          {data.payments.map((p, j) => (
            <div key={`${p.date}-${j}`} className="kv">
              <span>
                {dayMonth(p.date)} · {p.plan} · {p.months} мес
                {!OK_PAY.has(p.status) && <em className="pay-st"> · {PAY_STATUS[p.status] ?? p.status}</em>}
              </span>
              <b>{rub(p.amount_rub)} ₽</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
