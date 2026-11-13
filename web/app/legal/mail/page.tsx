export const metadata = { title: "служебная почта · crs·vpn" };

const sections = [
  {
    title: "Для чего используется Google",
    text: "CRS-VPN-Mail отправляет служебные письма CRS VPN: подтверждение email и ссылки сброса пароля. К приложению подключается только Gmail владельца сервиса. Пользователям сайта не нужно предоставлять доступ к своим почтовым ящикам.",
  },
  {
    title: "Разрешение и данные",
    text: "Приложение запрашивает только разрешение gmail.send, отправку писем от имени подключенного владельцем аккаунта. Оно не запрашивает чтение входящих писем, управление ящиком, контактами или Google Drive. Google получает адрес получателя и содержание отправляемого письма, включая одноразовую ссылку. Запись письма и статус доставки сохраняются в базе сайта.",
  },
  {
    title: "Доступ и защита",
    text: "OAuth-токен хранится в приватной конфигурации сервера, не публикуется и не передается пользователям сайта. Обмен с Google идет по HTTPS. Данные Google API используются для служебной отправки, не продаются и не используются для рекламы или обучения моделей. Использование данных Google API соответствует Google API Services User Data Policy, включая требования Limited Use.",
  },
  {
    title: "Отключение и обращения",
    text: "Владелец подключенного Gmail может отозвать доступ CRS-VPN-Mail в настройках Google Account, после чего отправка потребует нового разрешения. Для запросов об отправленных письмах и связанных данных сайта напиши на dcfrqb@gmail.com. Не присылай пароль или действующую ссылку сброса. Отзыв доступа Google сам по себе не удаляет записи сайта, запрос на их удаление рассматривается отдельно.",
  },
];

export default function MailPrivacyPage() {
  return (
    <main className="wrap band">
      <article style={{ maxWidth: "70ch", fontSize: 18, lineHeight: 1.65, overflowWrap: "anywhere" }}>
        <p className="caps">CRS-VPN-Mail</p>
        <h1 style={{ fontSize: "clamp(32px, 5vw, 64px)", lineHeight: 1.15 }}>Служебная почта</h1>
        <p style={{ marginTop: 24 }}>Правила использования Gmail API для отправки писем сайта CRS VPN.</p>
        {sections.map(({ title, text }) => (
          <section key={title} style={{ marginTop: 28 }}>
            <h2 style={{ fontSize: 24, lineHeight: 1.3 }}>{title}</h2>
            <p style={{ marginTop: 12 }}>{text}</p>
          </section>
        ))}
        <p style={{ marginTop: 28 }}>
          <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>
          {" · "}<a href="https://myaccount.google.com/connections">Доступ приложений Google</a>
        </p>
        <p><a href="mailto:dcfrqb@gmail.com">dcfrqb@gmail.com</a>{" · "}<a href="/">На главную</a></p>
      </article>
    </main>
  );
}
