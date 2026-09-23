import InnerHeader from "@/components/InnerHeader";
import CabinetView from "@/components/cabinet/CabinetView";
import LinkTelegram from "@/components/cabinet/LinkTelegram";
import { TG_BOT } from "@/lib/config";
import { getCabinet, requireAccount } from "@/lib/session";

export const metadata = { title: "кабинет · crs·vpn" };
export const dynamic = "force-dynamic";

function Down() {
  return (
    <div className="panel empty">
      <h4>кабинет сейчас не отвечает</h4>
      <p className="note">сервер недоступен. обнови страницу через минуту.</p>
    </div>
  );
}

export default async function CabinetPage() {
  const account = await requireAccount("/cabinet");
  const cab = account ? await getCabinet() : null;
  const data = cab?.state === "ok" ? cab.data : null;
  const demo = !!data?.demo && data.linked;
  const who = account?.telegram?.username ? `@${account.telegram.username}` : account?.telegram?.first_name || account?.email || "";

  return (
    <>
      <InnerHeader signedIn={!!account} />
      <main className="wrap band cabinet-page">
        <div className="sec-head">
          <h2>
            кабинет {demo && <span className="example">пример</span>}
          </h2>
          <p>
            {who && <span className="mono who">{who}</span>}
            {demo && <> данные ненастоящие: кабинет пока показывает пример, реальная подписка из бота появится позже.</>}
          </p>
        </div>

        {!account || !data ? (
          <Down />
        ) : !data.linked ? (
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
        ) : (
          <CabinetView data={data} />
        )}
      </main>
    </>
  );
}
