import InnerHeader from "@/components/InnerHeader";
import CabinetView from "@/components/cabinet/CabinetView";
import LinkTelegram from "@/components/cabinet/LinkTelegram";
import { TG_BOT } from "@/lib/config";
import { getCabinet, requireAccount } from "@/lib/session";
import { DEMO_SCENARIOS, type DemoScenario } from "@/lib/types";

export const metadata = { title: "кабинет · crs·vpn" };
export const dynamic = "force-dynamic";

function Down({ bot }: { bot: boolean }) {
  return (
    <div className="panel empty">
      <h4>{bot ? "бот не отвечает" : "кабинет сейчас не отвечает"}</h4>
      <p className="note">{bot ? "данные подписки живут в боте, а он сейчас молчит. обнови страницу через минуту." : "сервер недоступен. обнови страницу через минуту."}</p>
    </div>
  );
}

const SCENARIO_LABEL: Record<DemoScenario, string> = { active: "активна", expiring: "скоро кончится", expired: "закончилась", none: "нет подписки" };

// Owner preview: /cabinet?demo=expiring renders mock data for a state the account is not in.
function DemoBar({ scenario }: { scenario: DemoScenario }) {
  return (
    <div className="cb-demo" role="note">
      <span>
        <i aria-hidden="true" />
        пример: {scenario}
      </span>
      <nav aria-label="Другие примеры">
        {DEMO_SCENARIOS.filter((s) => s !== scenario).map((s) => (
          <a key={s} href={`/cabinet?demo=${s}`}>
            {SCENARIO_LABEL[s]}
          </a>
        ))}
      </nav>
      <a className="out" href="/cabinet">
        выйти из примера
      </a>
    </div>
  );
}

export default async function CabinetPage({ searchParams }: { searchParams: Promise<{ demo?: string | string[] }> }) {
  const raw = (await searchParams).demo;
  const scenario = (DEMO_SCENARIOS as readonly string[]).includes(String(raw)) ? (raw as DemoScenario) : null;
  const account = await requireAccount(scenario ? `/cabinet?demo=${scenario}` : "/cabinet");
  const cab = account ? await getCabinet(scenario) : null;
  const res = cab?.state === "ok" ? cab.data : null;
  const botDown = cab?.state === "down" && cab.status === 503;
  const demo = !!res?.demo && res.linked && !scenario;
  const who = account?.telegram?.username ? `@${account.telegram.username}` : account?.telegram?.first_name || account?.email || "";

  return (
    <>
      <InnerHeader signedIn={!!account} />
      <main className="wrap band cabinet-page">
        {scenario && <DemoBar scenario={scenario} />}
        <div className="sec-head">
          <h2>
            кабинет {demo && <span className="example">пример</span>}
          </h2>
          <p>
            {who && <span className="mono who">{who}</span>}
            {demo && <> данные ненастоящие: сайт пока не подключен к боту и показывает пример.</>}
          </p>
        </div>

        {res?.data?.partial && (
          <p className="cb-partial">
            {res.data.errors.includes("panel") ? "часть данных временно недоступна, показываем что есть." : "подписка и трафик из панели. оплаты и ru-вход появятся после обновления бота."}
          </p>
        )}

        {!account || !res ? (
          <Down bot={botDown} />
        ) : !res.linked ? (
          <div className="empty-grid">
            <div className="panel empty">
              <div className="caps step">01</div>
              <h4>привяжи telegram</h4>
              <p className="note">подписка живет в боте @{TG_BOT}. привяжи тот же telegram, и она появится здесь: дни, трафик, устройства, оплаты.</p>
              <LinkTelegram />
            </div>
            <div className="panel empty">
              <div className="caps step">02</div>
              <h4>или выбери тариф</h4>
              <p className="note">если подписки еще нет, начни с тарифа. оплата через сбп или карту.</p>
              <a className="btn solid" href="/#plans">
                выбрать тариф
              </a>
            </div>
          </div>
        ) : !res.data ? (
          <div className="empty-grid">
            <div className="panel empty">
              <div className="caps step">00</div>
              <h4>в боте пока нет подписки</h4>
              <p className="note">telegram привязан, но в @{TG_BOT} на него еще ничего не оформлено. выбери тариф, и подписка появится здесь.</p>
              <a className="btn solid" href="/#plans">
                выбрать тариф
              </a>
            </div>
          </div>
        ) : (
          <CabinetView data={res.data} />
        )}
      </main>
    </>
  );
}
