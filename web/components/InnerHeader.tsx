import LogoutButton from "@/components/auth/LogoutButton";

export default function InnerHeader({ signedIn }: { signedIn: boolean }) {
  return (
    <div className="wrap">
      <header className="inner-nav">
        <a className="brand" href="/">
          crs<b className="logo-dot" aria-hidden="true" />vpn
        </a>
        <nav className="inner-links" aria-label="Кабинет">
          {signedIn ? (
            <>
              <a href="/cabinet">кабинет</a>
              <a href="/cabinet/settings">настройки</a>
              <LogoutButton />
            </>
          ) : (
            <>
              <a href="/#plans">тарифы</a>
              <a href="/login">вход</a>
            </>
          )}
        </nav>
      </header>
      <hr className="hair" />
    </div>
  );
}
