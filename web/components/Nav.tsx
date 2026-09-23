type Props = { nodes: number; countries: number };

export default function Nav({ nodes, countries }: Props) {
  return (
    <nav className="nav" aria-label="Разделы">
      <a className="brand" href="#top">
        crs<b className="logo-dot" aria-hidden="true" />vpn
        <br />
        <span className="pn">private network</span>
      </a>
      <a className="navitem" href="#plans">
        <svg viewBox="0 0 34 34" aria-hidden="true">
          <rect x="3" y="3" width="12" height="12" fill="#0f0e12" />
          <rect x="19" y="3" width="12" height="12" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
          <rect x="3" y="19" width="12" height="12" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
          <circle cx="25" cy="25" r="6" fill="#f05a24" />
        </svg>
        <span>
          <span className="t">тарифы</span>
          <span className="s">
            lite / standard / pro
            <br />
            периоды и цены
            <br />
            способы оплаты
          </span>
        </span>
      </a>
      <a className="navitem" href="#specs">
        <svg viewBox="0 0 34 34" aria-hidden="true">
          <circle cx="17" cy="17" r="13" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
          <ellipse cx="17" cy="17" rx="6" ry="13" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
          <line x1="4" y1="17" x2="30" y2="17" stroke="#0f0e12" strokeWidth="1.5" />
        </svg>
        <span>
          <span className="t">сеть</span>
          <span className="s">
            узлы и страны
            <br />
            приложения
            <br />
            статус
          </span>
        </span>
      </a>
      <a className="navitem" href="/cabinet">
        <svg viewBox="0 0 34 34" aria-hidden="true">
          <rect x="3" y="5" width="28" height="18" rx="2" fill="#0f0e12" />
          <rect x="7" y="9" width="10" height="2" fill="#f05a24" />
          <rect x="7" y="14" width="16" height="2" fill="#f6f8f7" />
          <rect x="12" y="26" width="10" height="3" fill="#0f0e12" />
        </svg>
        <span>
          <span className="t">кабинет</span>
          <span className="s">
            подписка
            <br />
            устройства
            <br />
            история оплат
          </span>
        </span>
      </a>
      <a className="navitem" href="/login">
        <svg viewBox="0 0 34 34" aria-hidden="true">
          <circle cx="12" cy="17" r="8" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
          <circle cx="12" cy="17" r="3" fill="#0f0e12" />
          <path d="M20 17h11M27 17v5M31 17v4" stroke="#0f0e12" strokeWidth="1.5" fill="none" />
        </svg>
        <span>
          <span className="t">вход</span>
          <span className="s">
            telegram
            <br />
            email и пароль
            <br />
            паскей
          </span>
        </span>
      </a>
      <div className="serial" aria-hidden="true">
        модель <b>crs–01</b>
        <br />
        серия 03 / 2026
        <br />
        {nodes} узлов · {countries} страны
        <br />
        xray · vless
        <br />
        сделано вручную
      </div>
    </nav>
  );
}
