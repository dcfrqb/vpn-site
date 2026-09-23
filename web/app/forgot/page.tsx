import AuthShell from "@/components/auth/AuthShell";
import ForgotForm from "@/components/auth/ForgotForm";

export const metadata = { title: "сброс пароля · crs·vpn" };

export default function ForgotPage() {
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
      <ForgotForm />
    </AuthShell>
  );
}
