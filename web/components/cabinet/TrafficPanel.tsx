"use client";

import { useState } from "react";
import TrafficChart, { type Bar } from "@/components/cabinet/TrafficChart";
import { dayMonth, gb, plural } from "@/lib/format";
import type { BotCabinet } from "@/lib/types";

const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
// "2026-09" → "сен 26"
const monthLabel = (m: string) => `${MONTHS[Number(m.slice(5, 7)) - 1] ?? m} ${m.slice(2, 4)}`;

const VISIBLE_NODES = 5;

function Nodes({ rows }: { rows: BotCabinet["traffic_by_node"] }) {
  const [all, setAll] = useState(false);
  if (rows.length === 0) return null;
  const sorted = [...rows].sort((a, b) => b.bytes_30d - a.bytes_30d);
  // Rows that round to 0.0 gb are noise; hide them when the list is long.
  const zero = (b: number) => gb(b) === "0.0";
  const hidden = sorted.length > VISIBLE_NODES ? sorted.filter((r) => zero(r.bytes_30d)) : [];
  const shown = all ? sorted : sorted.filter((r) => !hidden.includes(r));
  const max = Math.max(...sorted.map((r) => r.bytes_30d), 1);
  return (
    <div className="cb-by-node">
      <div className="caps">по нодам, 30 дней</div>
      {shown.map((r) => (
        <div key={r.node} className="row">
          <span className="cc mono">{r.country ?? "··"}</span>
          <span className="nm mono" title={r.node}>
            {r.node}
          </span>
          <span className="track" aria-hidden="true">
            <i style={{ width: `${Math.max(2, (r.bytes_30d / max) * 100)}%` }} />
          </span>
          <b className="mono">{gb(r.bytes_30d)} гб</b>
        </div>
      ))}
      {hidden.length > 0 && (
        <button type="button" className="linkish cb-more" onClick={() => setAll((v) => !v)} aria-expanded={all}>
          {all ? "скрыть пустые" : `показать все (${sorted.length})`}
        </button>
      )}
    </div>
  );
}

export default function TrafficPanel({ data, obhod }: { data: BotCabinet }& { obhod: boolean }) {
  const [mode, setMode] = useState<"30d" | "all">("30d");
  const days = data.traffic_daily;
  const months = data.traffic_monthly ?? [];
  const noDaily = days.length === 0 || (data.partial && days.every((d) => d.main_bytes + d.obhod_bytes === 0));
  const total30 = days.reduce((a, d) => a + d.main_bytes + d.obhod_bytes, 0);
  const lifetimeParts = data.subscriptions.map((s) => s.traffic?.lifetime_used_bytes).filter((v): v is number => v != null);
  const monthsSum = months.reduce((a, m) => a + m.main_bytes + m.obhod_bytes, 0);
  const lifetime = lifetimeParts.length ? lifetimeParts.reduce((a, b) => a + b, 0) : months.length ? monthsSum : null;

  const dayBars: Bar[] = days.map((d) => ({ key: d.date, tip: dayMonth(d.date), main: d.main_bytes, obhod: d.obhod_bytes }));
  const monthBars: Bar[] = months.map((m) => ({ key: m.month, tip: monthLabel(m.month), main: m.main_bytes, obhod: m.obhod_bytes }));

  return (
    <>
      <div className="cb-head">
        <h4>
          трафик{" "}
          {mode === "30d" && !noDaily && (
            <span className="mono count">
              30 {plural(30, "день", "дня", "дней")} · {gb(total30)} гб
            </span>
          )}
          {mode === "all" && lifetime != null && <span className="mono count">все время · {gb(lifetime)} гб</span>}
        </h4>
        <div className="seg" role="group" aria-label="Период трафика">
          <button type="button" aria-pressed={mode === "30d"} onClick={() => setMode("30d")}>
            30 дней
          </button>
          <button type="button" aria-pressed={mode === "all"} onClick={() => setMode("all")}>
            все время
          </button>
        </div>
      </div>

      {mode === "30d" ? (
        noDaily ? (
          <p className="note">статистика трафика сейчас недоступна.</p>
        ) : (
          <TrafficChart bars={dayBars} axis={[dayMonth(days[0].date), dayMonth(days[Math.floor(days.length / 2)].date), "сегодня"]} unit="гб в день" obhod={obhod} label={`трафик по дням за ${days.length} дней`} />
        )
      ) : months.length === 0 ? (
        <p className="note">{data.partial ? "помесячная статистика сейчас недоступна." : "помесячная статистика еще считается. обнови страницу через минуту."}</p>
      ) : (
        <>
          <TrafficChart
            bars={monthBars}
            axis={[monthLabel(months[0].month), months.length > 2 ? monthLabel(months[Math.floor(months.length / 2)].month) : "", "этот месяц"]}
            unit="гб в месяц"
            obhod={obhod}
            label={`трафик по месяцам, ${months.length} ${plural(months.length, "месяц", "месяца", "месяцев")}`}
          />
          <div className="cb-sum">
            <div>
              <span className="caps">за все время</span>
              <b className="mono">{lifetime != null ? `${gb(lifetime)} гб` : "—"}</b>
            </div>
            <div>
              <span className="caps">в месяц</span>
              <b className="mono">~{gb(monthsSum / months.length, 0)} гб</b>
            </div>
            <div>
              <span className="caps">первый месяц</span>
              <b className="mono">{monthLabel(months[0].month)}</b>
            </div>
          </div>
        </>
      )}
      <Nodes rows={data.traffic_by_node.filter((r) => r.bytes_30d > 0)} />
    </>
  );
}
