import AuthShell from "@/components/auth/AuthShell";
import ResetForm from "@/components/auth/ResetForm";

export const metadata = { title: "новый пароль · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function ResetPage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const raw = (await searchParams).token;
  const token = typeof raw === "string" ? raw : "";

  return (
    <AuthShell code="crs–01 · сброс" title="новый пароль" lede={<p>после смены пароля все старые входы завершатся на всех устройствах.</p>}>
      {token ? (
        <ResetForm token={token} />
      ) : (
        <div className="form">
          <p className="form-err">в ссылке нет кода. открой ссылку из письма целиком или запроси новую.</p>
          <a className="btn wide" href="/forgot">
            запросить ссылку
          </a>
        </div>
      )}
    </AuthShell>
  );
}
