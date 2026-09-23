"use client";

import { useState } from "react";

const EXITS = [
  { code: "NL", node: "NL–1", ms: 38, tag: "EXIT" },
  { code: "FR", node: "FR–2", ms: 44, tag: "EXIT" },
  { code: "US", node: "US–3", ms: 112, tag: "EXIT" },
  { code: "ES", node: "ES–1", ms: 61, tag: "EXIT" },
  { code: "RU", node: "RU–1", ms: 9, tag: "PRO" },
] as const;

const MONO = "var(--mono)";

export default function Device() {
  const [on, setOn] = useState(true);
  const [current, setCurrent] = useState<(typeof EXITS)[number]["code"]>("NL");
  const exit = EXITS.find((e) => e.code === current)!;
  const level = on ? Math.max(3, Math.round(13 - exit.ms / 12)) : 0;

  const onKey = (fn: () => void) => (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fn();
    }
  };

  return (
    <figure className="device" style={{ margin: 0 }}>
      <svg viewBox="0 0 420 540" role="img" aria-label="Схема устройства CRS–01: дисплей, клавиши стран, кнопка питания">
        <rect x="6" y="6" width="408" height="528" rx="30" fill="#e3e5e4" stroke="#c9cccb" />
        <g fill="#c2c5c4">
          <circle cx="30" cy="30" r="5" />
          <circle cx="390" cy="30" r="5" />
          <circle cx="30" cy="510" r="5" />
          <circle cx="390" cy="510" r="5" />
        </g>

        <rect x="40" y="46" width="240" height="160" rx="10" fill="#0f0e12" />
        <text x="56" y="74" fontFamily={MONO} fontSize="11" letterSpacing="1" fill={on ? "#f05a24" : "#6d6c73"}>
          {on ? "● ON" : "○ OFF"}
        </text>
        <text x="264" y="74" textAnchor="end" fontFamily={MONO} fontSize="11" letterSpacing="1" fill="#6d6c73">
          CRS–01
        </text>
        <text x="56" y="128" fontFamily={MONO} fontSize="40" fontWeight="200" fill="#f2f2ee" letterSpacing="-1">
          {on ? exit.node : "— — —"}
        </text>
        <text x="56" y="152" fontFamily={MONO} fontSize="12" fill="#6d6c73" letterSpacing="1">
          {on ? `PING ${exit.ms} MS · XHTTP` : "НЕТ СОЕДИНЕНИЯ"}
        </text>
        <g className="vu">
          {Array.from({ length: 16 }, (_, i) => (
            <rect key={i} x={56 + i * 13.4} y="176" width="9" height="14" rx="1" fill={i > 12 ? "#f05a24" : "#f2f2ee"} opacity={i < level ? 1 : 0.18} />
          ))}
        </g>

        <g>
          {Array.from({ length: 54 }, (_, i) => (
            <circle key={i} cx={306 + (i % 6) * 16} cy={58 + Math.floor(i / 6) * 17} r="4.2" fill="#2a292e" />
          ))}
        </g>

        <text x="40" y="238" fontFamily={MONO} fontSize="10" letterSpacing="1.5" fill="#6d6c73">
          ВЫХОД / EXIT NODE
        </text>
        <line x1="40" y1="246" x2="380" y2="246" stroke="#b2b2b2" />
        {EXITS.map((e, idx) => {
          const x = 40 + idx * 69;
          const y = 262;
          const active = e.code === current;
          const pick = () => {
            setCurrent(e.code);
            setOn(true);
          };
          return (
            <g key={e.code} className={`dkey${active ? " on" : ""}`} role="button" tabIndex={0} aria-label={`Выход ${e.code}`} aria-pressed={active} onClick={pick} onKeyDown={onKey(pick)}>
              <rect x={x} y={y} width="58" height="58" rx="9" fill="#bfc2c1" />
              <rect className="face" x={x + 3} y={y + 2} width="52" height="52" rx="8" fill="#2a292e" />
              <text x={x + 29} y={y + 34} textAnchor="middle" fontFamily={MONO} fontSize="15" fill="#f2f2ee" letterSpacing="1">
                {e.code}
              </text>
              <circle cx={x + 29} cy={y + 72} r="3.5" fill={active && on ? "#f05a24" : "#bfc2c1"} />
              <text x={x + 29} y={y + 92} textAnchor="middle" fontFamily={MONO} fontSize="8.5" fill="#9a9da0" letterSpacing="1">
                {e.tag}
              </text>
            </g>
          );
        })}

        <text x="40" y="382" fontFamily={MONO} fontSize="10" letterSpacing="1.5" fill="#6d6c73">
          ПИТАНИЕ
        </text>
        <text x="236" y="382" fontFamily={MONO} fontSize="10" letterSpacing="1.5" fill="#6d6c73">
          УСТРОЙСТВА
        </text>
        <line x1="40" y1="390" x2="380" y2="390" stroke="#b2b2b2" />
        <g id="power" role="button" tabIndex={0} aria-label={on ? "Выключить" : "Включить"} aria-pressed={on} onClick={() => setOn(!on)} onKeyDown={onKey(() => setOn(!on))}>
          <circle cx="104" cy="452" r="50" fill="#cfd2d1" />
          <circle className="ring" cx="104" cy="452" r="40" fill={on ? "#f05a24" : "#8c8f8e"} />
          <circle cx="104" cy="452" r="40" fill="none" stroke="#000" strokeOpacity=".12" />
          <path d="M104 432v16M92 440a17 17 0 1 0 24 0" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" />
        </g>
        <circle cx="206" cy="452" r="22" fill="#cfd2d1" />
        <circle cx="206" cy="452" r="16" fill="#f6f8f7" />
        <line x1="206" y1="440" x2="206" y2="448" stroke="#0f0e12" strokeWidth="2" />
        {Array.from({ length: 5 }, (_, s) => (
          <rect key={s} x={246 + s * 27} y="438" width="20" height="28" rx="4" fill={s < 3 ? "#0f0e12" : "none"} stroke="#9a9da0" />
        ))}
        <text x="380" y="512" textAnchor="end" fontFamily={MONO} fontSize="9" letterSpacing="1.5" fill="#9a9da0">
          MADE BY CRS · 03
        </text>
      </svg>
      <figcaption className="cap caps">
        <span>нажми на страну</span>
        <span>схема, не фото</span>
      </figcaption>
    </figure>
  );
}
