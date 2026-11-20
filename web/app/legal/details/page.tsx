import LegalPage from "@/components/legal/LegalPage";

export const dynamic = "force-dynamic";
export const metadata = { title: "реквизиты · crs·vpn", robots: { index: false, follow: false } };

export default function DetailsPage() {
  // Runtime server values, never baked into browser bundles or kept in the public repository.
  const name = process.env.LEGAL_SELLER_NAME;
  const inn = process.env.LEGAL_SELLER_INN;
  const address = process.env.LEGAL_SELLER_ADDRESS;
  return <LegalPage document={{ title: "реквизиты", intro: "Исполнитель и оператор персональных данных CRS VPN.", draft: true, sections: [] }}>
    <dl>
      <dt>сервис</dt><dd>CRS VPN</dd>
      <dt>исполнитель</dt><dd>{name || "будет указан перед утверждением документов"}</dd>
      <dt>статус</dt><dd>плательщик налога на профессиональный доход (самозанятый)</dd>
      <dt>ИНН</dt><dd>{inn || "будет указан перед утверждением документов"}</dd>
      <dt>адрес для обращений</dt><dd>{address || "требует уточнения перед утверждением документов"}</dd>
      <dt>email</dt><dd><a href="mailto:dcfrqb@gmail.com">dcfrqb@gmail.com</a></dd>
      <dt>telegram</dt><dd><a href="https://t.me/dcfrq">@dcfrq</a></dd>
    </dl>
  </LegalPage>;
}
