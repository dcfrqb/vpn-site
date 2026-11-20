import InnerHeader from "@/components/InnerHeader";
import { LEGAL_VERSION, type LegalDocument } from "@/lib/legal-documents";

export default function LegalPage({ document, children }: { document: LegalDocument; children?: React.ReactNode }) {
  return <>
    <InnerHeader signedIn={false} />
    <main className="wrap legal">
      <p className="caps">crs–01 · документы</p>
      <h1>{document.title}</h1>
      <p>{document.intro}</p>
      {document.draft && <aside className="legal-note" aria-label="Статус документа">
        <p>Проект для проверки, версия {LEGAL_VERSION}. До утверждения он не применяется к действующим покупкам. Условия требуют проверки правовой модели сервиса, реквизитов и обработки данных.</p>
      </aside>}
      <nav aria-label="Документы">
        <a href="/legal/offer">оферта</a><a href="/legal/privacy">данные</a><a href="/legal/consent">согласие</a><a href="/legal/cookies">cookie</a><a href="/legal/refunds">возвраты</a><a href="/legal/details">реквизиты</a>
      </nav>
      {children}
      {document.sections.map((section) => <section key={section.title}>
        <h2>{section.title}</h2>
        {section.paragraphs.map((p) => <p key={p}>{p}</p>)}
      </section>)}
      <p><a href="mailto:dcfrqb@gmail.com">dcfrqb@gmail.com</a> · <a href="https://t.me/dcfrq">telegram: @dcfrq</a></p>
      <p><a href="/">на главную</a></p>
    </main>
  </>;
}
