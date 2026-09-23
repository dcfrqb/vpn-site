import { gb, GB } from "@/lib/format";

export type Bar = { key: string; tip: string; main: number; obhod: number };

// Round axis maximum in GB: 1, 2, 5, 10, 20, 50 ...
function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * p) return m * p;
  return 10 * p;
}

const fmtTick = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

// Inline SVG, drawn to scale: bar heights are bytes / axis max. Bars stretch with the width,
// labels are plain HTML so they keep their size on a phone. The last bar (today, this month)
// is lit with the accent.
export default function TrafficChart({ bars, axis, unit, obhod, label }: { bars: Bar[]; axis: [string, string, string]; unit: string; obhod: boolean; label: string }) {
  const W = 300;
  const H = 120;
  const n = bars.length;
  const slot = W / Math.max(n, 1);
  const bw = Math.max(1, slot * (n < 8 ? 0.5 : 0.72));
  const max = niceMax(Math.max(...bars.map((d) => (d.main + d.obhod) / GB)));
  const ticks = [max, max / 2, 0];
  const y = (gbv: number) => H - (gbv / max) * H;
  const peak = bars.reduce((a, d) => Math.max(a, d.main + d.obhod), 0);

  return (
    <figure className="cb-chart" aria-label={`${label}, максимум ${gb(peak)} гб`}>
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
          {bars.map((d, i) => {
            const m = d.main / GB;
            const o = d.obhod / GB;
            const x = i * slot + (slot - bw) / 2;
            const last = i === n - 1;
            return (
              <g key={d.key}>
                <title>{`${d.tip} · ${gb(d.main)} гб${obhod ? ` + ru-вход ${gb(d.obhod)} гб` : ""}`}</title>
                {m > 0 && <rect x={x} width={bw} y={y(m)} height={H - y(m)} className={last ? "today" : "main"} />}
                {o > 0 && <rect x={x} width={bw} y={y(m + o)} height={H - y(o)} className="obhod" />}
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption>
        <div className="xaxis" aria-hidden="true">
          {axis.map((a, i) => (
            <span key={i}>{a}</span>
          ))}
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
          <span className="unit">{unit}</span>
        </div>
      </figcaption>
    </figure>
  );
}
