import InnerHeader from "@/components/InnerHeader";

type Props = { signedIn?: boolean; code: string; title: string; lede: React.ReactNode; children: React.ReactNode; aside?: React.ReactNode };

// Two columns on desktop (headline left, form card right), one column on phones.
export default function AuthShell({ code, title, lede, children, aside, signedIn = false }: Props) {
  return (
    <>
      <InnerHeader signedIn={signedIn} />
      <main className="wrap auth">
        <div className="auth-head">
          <div className="eyebrow caps">
            <i /> {code}
          </div>
          <h2>{title}</h2>
          <div className="auth-lede">{lede}</div>
          {aside}
        </div>
        <div className="auth-card">{children}</div>
      </main>
    </>
  );
}
