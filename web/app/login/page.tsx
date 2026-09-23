import AuthShell from "@/components/auth/AuthShell";
import LoginForm from "@/components/auth/LoginForm";
import PasskeyLogin from "@/components/auth/PasskeyLogin";
import TelegramLogin from "@/components/auth/TelegramLogin";
import { safeNext } from "@/lib/next-path";
import { redirectIfSignedIn } from "@/lib/session";

export const metadata = { title: "вход · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const next = safeNext((await searchParams).next);
  await redirectIfSignedIn(next);
  const q = next === "/cabinet" ? "" : `?next=${encodeURIComponent(next)}`;

  return (
    <AuthShell
      code="crs–01 · вход"
      title="вход"
      lede={
        <p>
          один аккаунт, три способа войти. если подписка уже есть в боте, войди через telegram, и она сразу появится в кабинете.
        </p>
      }
      aside={
        <p className="auth-alt">
          нет аккаунта? <a href={`/register${q}`}>зарегистрируйся по email</a>
        </p>
      }
    >
      <section className="method">
        <h3 className="caps">01 · telegram</h3>
        <TelegramLogin mode="login" next={next} />
      </section>
      <section className="method">
        <h3 className="caps">02 · email и пароль</h3>
        <LoginForm next={next} />
      </section>
      <section className="method">
        <h3 className="caps">03 · паскей</h3>
        <PasskeyLogin next={next} />
        <p className="note">face id, отпечаток или ключ. паскей добавляется в настройках после первого входа.</p>
      </section>
    </AuthShell>
  );
}
