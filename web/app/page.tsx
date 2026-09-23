import CabinetPreview from "@/components/CabinetPreview";
import CookiePlate from "@/components/CookiePlate";
import Device from "@/components/Device";
import Nav from "@/components/Nav";
import Plans from "@/components/Plans";
import { getNetwork, getPlans } from "@/lib/api";

export const dynamic = "force-dynamic";

const COUNTRY_RU: Record<string, string> = { nl: "нидерланды", fr: "франция", us: "сша", es: "испания" };
const pad = (n: number) => String(n).padStart(2, "0");

export default async function Home() {
  const [plans, net] = await Promise.all([getPlans(), getNetwork()]);
  const nodes = net?.nodes_total ?? 9;
  const exits = net?.exit_countries ?? ["nl", "fr", "us", "es"];
  const minPrice = plans ? Math.min(...plans.map((p) => p.prices["1"])) : null;
  const maxDevices = plans ? Math.max(...plans.map((p) => p.device_limit)) : 10;

  return (
    <>
      <div className="wrap">
        <Nav nodes={nodes} countries={exits.length} />
        <hr className="hair" />
        <section className="hero" id="top">
          <div>
            <div className="eyebrow caps">
              <i /> crs–01 · private network
            </div>
            <h1>
              подключил
              <br />и <em>забыл.</em>
            </h1>
            <p className="lede">частная сеть на своих серверах в {exits.length} странах. одна ссылка на все устройства, без лимита трафика и рекламы на youtube.</p>
            <div className="btns">
              <a className="btn solid" href="#plans">
                выбрать тариф {minPrice && <span className="k">от {minPrice} ₽</span>}
              </a>
              <a className="btn" href="#login">
                войти
              </a>
            </div>
          </div>
          <Device />
        </section>
      </div>

      <hr className="hair" />

      <section className="band" id="specs">
        <div className="wrap">
          <div className="sec-head">
            <h2>что внутри</h2>
            <p>никаких «сверхскоростей» и «военного шифрования». вот из чего сеть собрана на самом деле.</p>
          </div>
          <div className="specs">
            <div className="spec">
              <span className="n">{pad(nodes)}</span>
              <span className="l">узлов в сети</span>
              <span className="d">свои серверы у четырех провайдеров, не аренда чужого сервиса</span>
            </div>
            <div className="spec">
              <span className="n">{pad(exits.length)}</span>
              <span className="l">страны выхода</span>
              <span className="d">{exits.map((c) => COUNTRY_RU[c] ?? c).join(", ")}</span>
            </div>
            <div className="spec">
              <span className="n">∞</span>
              <span className="l">трафик</span>
              <span className="d">без лимита на всех тарифах, без урезания скорости</span>
            </div>
            <div className="spec">
              <span className="n">01</span>
              <span className="l">ссылка</span>
              <span className="d">одна подписка на телефон, ноутбук и телевизор</span>
            </div>
            <div className="spec">
              <span className="n">{pad(maxDevices)}</span>
              <span className="l">устройств максимум</span>
              <span className="d">зависит от тарифа</span>
            </div>
            <div className="spec">
              <span className="n">03</span>
              <span className="l">минуты</span>
              <span className="d">так часто проверяется каждый узел, сбой видно сразу</span>
            </div>
          </div>
        </div>
      </section>

      <section className="band dark" id="plans">
        <div className="wrap">
          <div className="sec-head">
            <h2>тарифы</h2>
            <p>три комплектации. чем дольше период, тем дешевле месяц.</p>
          </div>
          {plans ? <Plans plans={plans} /> : <p className="muted-note">тарифы временно недоступны, попробуй обновить страницу через минуту.</p>}
          <p className="foot-note">* формулировку для pro согласуем с юристом.</p>
          <div className="pay-row caps">
            <span>оплата: сбп · карта</span>
            <span>через юkassa</span>
            <span>чек на email по 54-фз</span>
            <span>автопродление можно выключить</span>
          </div>
        </div>
      </section>

      <section className="band" id="cabinet">
        <div className="wrap">
          <div className="sec-head">
            <h2>
              кабинет <span className="example">пример</span>
            </h2>
            <p>экран устройства, а не таблица: сколько дней осталось, сколько трафика ушло, какие узлы живы. ссылку на подписку копируешь в одно нажатие.</p>
          </div>
          <CabinetPreview />
        </div>
      </section>

      <hr className="hair" />

      <section className="band" id="login">
        <div className="wrap">
          <div className="sec-head">
            <h2>вход</h2>
            <p>один аккаунт, три способа войти. если в боте уже есть подписка, после входа через telegram она сразу появится здесь.</p>
          </div>
          <div className="login">
            <div className="lg">
              <svg viewBox="0 0 40 40" aria-hidden="true">
                <circle cx="20" cy="20" r="18" fill="#0f0e12" />
                <path d="M10 19.5l18-7-3 16-5.5-4.2-3 2.9.4-4.6 8.2-7.6-10 6.3z" fill="#f6f8f7" />
              </svg>
              <h3>telegram</h3>
              <p>подтверждение в самом telegram, пароль не нужен. аккаунт сразу связан с ботом.</p>
              <button className="btn solid" type="button" disabled>
                скоро
              </button>
            </div>
            <div className="lg">
              <svg viewBox="0 0 40 40" aria-hidden="true">
                <rect x="3" y="8" width="34" height="24" rx="3" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
                <path d="M3 10l17 12 17-12" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
              </svg>
              <h3>email и пароль</h3>
              <p>для тех, у кого нет telegram. telegram можно привязать позже, в настройках.</p>
              <button className="btn" type="button" disabled>
                скоро
              </button>
            </div>
            <div className="lg">
              <svg viewBox="0 0 40 40" aria-hidden="true">
                <circle cx="15" cy="13" r="7" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
                <path d="M3 34c1-7 6-11 12-11 3 0 5.5 1 7.5 2.5" fill="none" stroke="#0f0e12" strokeWidth="1.5" />
                <circle cx="30" cy="25" r="4" fill="#f05a24" />
                <path d="M30 29v7m0-3h3" stroke="#0f0e12" strokeWidth="1.5" fill="none" />
              </svg>
              <h3>паскей</h3>
              <p>face id или отпечаток пальца. добавляется в кабинете после первого входа.</p>
              <button className="btn" type="button" disabled>
                скоро
              </button>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div className="wrap fgrid">
          <div>
            <div className="fbrand">
              crs<b>·</b>vpn
            </div>
            <p style={{ margin: "12px 0 0", maxWidth: "30ch" }}>реквизиты продавца появятся здесь после проверки юристом.</p>
          </div>
          <div>
            <h5>документы</h5>
            <a href="/legal/cookies">публичная оферта</a>
            <a href="/legal/cookies">политика обработки данных</a>
            <a href="/legal/cookies">cookie</a>
          </div>
          <div>
            <h5>помощь</h5>
            <a href="#top">как подключить</a>
            <a href="#top">частые вопросы</a>
            <a href="#top">поддержка в telegram</a>
          </div>
          <div>
            <h5>статус</h5>
            <a href="#specs">{net ? `${net.nodes_online} из ${net.nodes_total} узлов на связи` : "статус недоступен"}</a>
          </div>
        </div>
      </footer>

      <CookiePlate />
    </>
  );
}
