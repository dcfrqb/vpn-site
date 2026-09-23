import { dayMonth, gb, GB } from "@/lib/format";
import type { BotCabinet } from "@/lib/types";

type Day = BotCabinet["traffic_daily"][number];

// Round axis maximum in GB: 1, 2, 5, 10, 20, 50 ...
function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * p) return m * p;
  return 10 * p;
}

const fmtTick = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

// Inline SVG, drawn to scale: bar heights are bytes / axis max. Bars stretch with the width,
// labels are plain HTML so they keep their size on a phone.
export default function TrafficChart({ days, obhod }: { days: Day[]; obhod: boolean }) {
  const W = 300;
  const H = 120;
  const n = days.length;
  const slot = W / n;
  const bw = Math.max(1, slot * 0.72);
  const max = niceMax(Math.max(...days.map((d) => (d.main_bytes + d.obhod_bytes) / GB)));
  const ticks = [max, max / 2, 0];
  const y = (gbv: number) => H - (gbv / max) * H;
  const peak = days.reduce((a, d) => Math.max(a, d.main_bytes + d.obhod_bytes), 0);

  return (
    <figure className="cb-chart" aria-label={`трафик по дням за ${n} дней, максимум ${gb(peak)} гб в день`}>
      <div className="plot">
        <div className="yaxis" aria-hidden="true">
          {ticks.map((t) => (
            <span key={t} style={{ top: `${(1 - t / max) * 100}%` }}>
              {fmtTick(t)}
            </span>
          ))}
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img">
          {ticks.map((t) => (
            <line key={t} x1="0" x2={W} y1={y(t)} y2={y(t)} className={t === 0 ? "base" : "grid"} vectorEffect="non-scaling-stroke" />
          ))}
          {days.map((d, i) => {
            const m = d.main_bytes / GB;
            const o = d.obhod_bytes / GB;
            const x = i * slot + (slot - bw) / 2;
            const last = i === n - 1;
            return (
              <g key={d.date}>
                <title>{`${dayMonth(d.date)} · ${gb(d.main_bytes)} гб${obhod ? ` + ru-вход ${gb(d.obhod_bytes)} гб` : ""}`}</title>
                {m > 0 && <rect x={x} width={bw} y={y(m)} height={H - y(m)} className={last ? "today" : "main"} />}
                {o > 0 && <rect x={x} width={bw} y={y(m + o)} height={H - y(o)} className="obhod" />}
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption>
        <div className="xaxis" aria-hidden="true">
          <span>{dayMonth(days[0].date)}</span>
          <span>{dayMonth(days[Math.floor(n / 2)].date)}</span>
          <span>сегодня</span>
        </div>
        <div className="legend">
          <span>
            <i className="sw main" /> основная
          </span>
          {obhod && (
            <span>
              <i className="sw obhod" /> ru-вход
            </span>
          )}
          <span className="unit">гб в день</span>
        </div>
      </figcaption>
    </figure>
  );
}
