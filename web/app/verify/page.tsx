import AuthShell from "@/components/auth/AuthShell";
import VerifyEmail from "@/components/auth/VerifyEmail";

export const metadata = { title: "подтверждение email · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function VerifyPage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const raw = (await searchParams).token;
  const token = typeof raw === "string" ? raw : "";

  return (
    <AuthShell code="crs–01 · email" title="подтверждение email" lede={<p>подтвержденный email нужен, чтобы восстановить доступ и получать чеки.</p>}>
      {token ? (
        <VerifyEmail token={token} />
      ) : (
        <div className="form">
          <p className="form-err">в ссылке нет кода. открой ссылку из письма целиком.</p>
          <a className="btn wide" href="/cabinet/settings">
            в настройки
          </a>
        </div>
      )}
    </AuthShell>
  );
}
