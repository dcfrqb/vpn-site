import AuthShell from "@/components/auth/AuthShell";
import RegisterForm from "@/components/auth/RegisterForm";
import { safeNext } from "@/lib/next-path";
import { redirectIfSignedIn } from "@/lib/session";

export const metadata = { title: "регистрация · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const next = safeNext((await searchParams).next);
  await redirectIfSignedIn(next);
  const q = next === "/cabinet" ? "" : `?next=${encodeURIComponent(next)}`;

  return (
    <AuthShell
      code="crs–01 · новый аккаунт"
      title="регистрация"
      lede={
        <p>
          аккаунт по email для тех, у кого нет telegram. подписку из бота увидишь, когда привяжешь telegram в настройках.
        </p>
      }
      aside={
        <p className="auth-alt">
          уже есть аккаунт? <a href={`/login${q}`}>войти</a>
        </p>
      }
    >
      <RegisterForm next={next} />
    </AuthShell>
  );
}
