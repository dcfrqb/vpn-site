import AuthShell from "@/components/auth/AuthShell";
import ForgotForm from "@/components/auth/ForgotForm";

export const metadata = { title: "сброс пароля · crs·vpn" };

export const dynamic = "force-dynamic";

export default async function ForgotPage({ searchParams }: { searchParams: Promise<{ email?: string | string[] }> }) {
  const raw = (await searchParams).email;
  const email = typeof raw === "string" ? raw.slice(0, 320) : "";
  return (
    <AuthShell
      code="crs–01 · сброс"
      title="забыл пароль"
      lede={<p>пришлем ссылку для нового пароля на email аккаунта. если входил через telegram, пароль не нужен, просто войди через него.</p>}
      aside={
        <p className="auth-alt">
          вспомнил? <a href="/login">войти</a>
        </p>
      }
    >
      <ForgotForm initialEmail={email} />
    </AuthShell>
  );
}
