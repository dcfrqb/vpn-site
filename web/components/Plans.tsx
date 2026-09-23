"use client";

import { useState } from "react";
import type { Plan } from "@/lib/api";

const PERIODS = [1, 3, 6, 12] as const;

function rub(n: number) {
  return n.toLocaleString("ru-RU");
}

export default function Plans({ plans }: { plans: Plan[] }) {
  const [months, setMonths] = useState<(typeof PERIODS)[number]>(1);

  return (
    <>
      <div className="period" role="group" aria-label="Период оплаты">
        {PERIODS.map((m) => (
          <button key={m} type="button" aria-pressed={m === months} onClick={() => setMonths(m)}>
            {m} мес
          </button>
        ))}
      </div>
      <div className="plans">
        {plans.map((p) => {
          const price = p.prices[String(months)];
          const base = p.prices["1"];
          const perMonth = Math.round(price / months);
          const saving = Math.round((1 - perMonth / base) * 100);
          return (
            <article key={p.code} className={`plan${p.highlighted ? " hl" : ""}`}>
              <div className="plan-top">
                <div>
                  <div className="code">
                    crs–01 / {p.code}
                    {p.highlighted ? " · чаще всего" : ""}
                  </div>
                  <h3>{p.title}</h3>
                </div>
                <span className="led" />
              </div>
              <div className="price">
                <span className="v">{rub(price)}</span>
                <span className="u">₽</span>
              </div>
              <div className="permo">{months === 1 ? "за месяц" : `${rub(perMonth)} ₽ в месяц · ${months} мес · выгода ${saving}%`}</div>
              <ul className="sheet">
                <li>
                  <span>устройства</span>
                  <span>{p.device_limit}</span>
                </li>
                <li>
                  <span>страны</span>
                  <span>{p.countries.join(" · ")}</span>
                </li>
                <li>
                  <span>трафик</span>
                  <span>без лимита</span>
                </li>
                <li>
                  <span>youtube</span>
                  <span>без рекламы</span>
                </li>
                <li>
                  <span>ru-вход{p.ru_entry_gb ? " *" : ""}</span>
                  <span>{p.ru_entry_gb ? `${p.ru_entry_gb} гб / мес` : "—"}</span>
                </li>
              </ul>
              <a className="btn" href="#login">
                выбрать {p.title}
              </a>
            </article>
          );
        })}
      </div>
    </>
  );
}
