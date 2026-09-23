export default function NotFound() {
  return (
    <main className="wrap band">
      <div className="caps" style={{ color: "var(--muted)" }}>ошибка 404</div>
      <h2 style={{ marginTop: 16 }}>такой страницы нет.</h2>
      <p>
        <a href="/">← на главную</a>
      </p>
    </main>
  );
}
