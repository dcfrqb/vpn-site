import InnerHeader from "@/components/InnerHeader";
import Settings from "@/components/settings/Settings";
import { getSessions, requireAccount } from "@/lib/session";

export const metadata = { title: "настройки · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const account = await requireAccount("/cabinet/settings");
  const sessions = account ? await getSessions() : null;

  return (
    <>
      <InnerHeader signedIn={!!account} />
      <main className="wrap band">
        <div className="sec-head">
          <h2>настройки</h2>
          <p>способы входа, email и открытые сессии. оставь хотя бы один способ входа, последний удалить нельзя.</p>
        </div>
        {account ? (
          <Settings account={account} sessions={sessions?.state === "ok" ? sessions.data : null} />
        ) : (
          <div className="panel empty">
            <h4>настройки сейчас не отвечают</h4>
            <p className="note">сервер недоступен. обнови страницу через минуту.</p>
          </div>
        )}
      </main>
    </>
  );
}
