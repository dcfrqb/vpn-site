// Fixed time zone so server and browser render the same text (no hydration mismatch).
const TZ = "Europe/Moscow";

function parts(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const f = new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" }).formatToParts(d);
  const get = (t: string) => f.find((p) => p.type === t)?.value ?? "";
  return { d, day: get("day"), month: get("month"), year: get("year") };
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  const p = parts(iso);
  return p ? `${p.day}.${p.month}.${p.year}` : "—";
}

export function dayMonth(iso: string): string {
  const p = parts(iso);
  return p ? `${p.day}.${p.month}` : "—";
}

export function plural(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}

function dayKey(d: Date) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "не заходило";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const today = new Date(dayKey(new Date()));
  const that = new Date(dayKey(d));
  const days = Math.round((today.getTime() - that.getTime()) / 86400000);
  if (days <= 0) return "сегодня";
  if (days === 1) return "вчера";
  if (days < 60) return `${days} ${plural(days, "день", "дня", "дней")} назад`;
  return date(iso);
}

export function monthName(now = new Date()): string {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, month: "long" }).format(now).toLowerCase();
}

export const rub = (n: number) => n.toLocaleString("ru-RU");

// "Mozilla/5.0 (iPhone; ...) ... Safari" → "safari · iphone"
export function shortAgent(ua: string | null | undefined): string {
  if (!ua) return "неизвестное устройство";
  const os = /iPhone/.test(ua) ? "iphone" : /iPad/.test(ua) ? "ipad" : /Android/.test(ua) ? "android" : /Mac OS X|Macintosh/.test(ua) ? "mac" : /Windows/.test(ua) ? "windows" : /Linux/.test(ua) ? "linux" : "";
  const br = /Edg\//.test(ua) ? "edge" : /YaBrowser/.test(ua) ? "яндекс браузер" : /Firefox\//.test(ua) ? "firefox" : /Chrome\//.test(ua) ? "chrome" : /Safari\//.test(ua) ? "safari" : "";
  const s = [br, os].filter(Boolean).join(" · ");
  return s || ua.slice(0, 40).toLowerCase();
}

export const GB = 1024 ** 3;

// Bytes → "12.3" (binary gigabytes, as the bot and the panel count them).
export function gb(bytes: number | null | undefined, digits = 1): string {
  if (bytes == null) return "—";
  const v = bytes / GB;
  if (v >= 1000) return Math.round(v).toLocaleString("ru-RU");
  return v.toFixed(v >= 100 ? 0 : digits);
}

// Last seen with minute precision: "только что", "12 мин назад", "3 ч назад", "вчера", ...
export function agoFine(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "не заходило";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const min = Math.floor((now - t) / 60000);
  if (min < 2) return "только что";
  if (min < 60) return `${min} мин назад`;
  if (min < 60 * 12) return `${Math.floor(min / 60)} ч назад`;
  return ago(iso);
}
