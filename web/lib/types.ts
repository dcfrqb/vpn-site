// Shapes from docs/stage-3-auth-cabinet.md (API contract). Shared by server and client code.

export type Passkey = { id: string; name: string | null; created_at: string; last_used_at: string | null };

export type Account = {
  id: string;
  email: string | null;
  email_verified: boolean;
  telegram: { id: number; username: string | null; first_name: string | null } | null;
  has_password: boolean;
  passkeys: Passkey[];
  created_at: string;
};

export type SessionInfo = {
  id: string;
  current: boolean;
  created_at: string;
  last_seen_at: string;
  ip: string | null;
  user_agent: string | null;
};

// Cabinet JSON (shape of Servers/docs/САЙТ_2026-09-23/bot-site-cabinet-api-spec.md), composed by the api
// from the bot profile and the Remnawave panel: see docs/cabinet-data.md.
export type SubKind = "main" | "obhod";
export type SubStatus = "active" | "expired" | "disabled" | "limited" | "pending" | "unknown";

export type CabinetSubscription = {
  kind: SubKind | string;
  plan_code: string | null;
  plan_title: string | null;
  legacy: boolean;
  status: SubStatus | string;
  valid_until: string | null;
  is_lifetime: boolean;
  days_left: number | null;
  device_limit: number | null;
  sub_url: string | null;
  traffic: { used_bytes: number | null; limit_bytes: number | null; reset: string; month_used_bytes: number | null } | null;
  package: { code: string; until: string | null; limit_bytes: number | null } | null;
  online_at: string | null;
  last_node: string | null;
};

export type CabinetDevice = {
  subscription: SubKind | string;
  hwid: string;
  platform: string | null;
  os_version: string | null;
  model: string | null;
  app: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
};

export type CabinetPayment = {
  id: number;
  created_at: string;
  paid_at: string | null;
  provider: string | null;
  status: string;
  amount_rub: number;
  plan_code: string | null;
  period_months: number | null;
  kind: "subscription" | "obhod_package" | "promo" | string;
  description: string | null;
};

export type BotCabinet = {
  generated_at: string;
  partial: boolean;
  errors: string[];
  user: { telegram_id: number; username: string | null; first_name: string | null; customer_since: string | null };
  subscriptions: CabinetSubscription[];
  devices: CabinetDevice[];
  traffic_daily: { date: string; main_bytes: number; obhod_bytes: number }[];
  traffic_by_node: { node: string; country: string | null; bytes_30d: number }[];
  payments: CabinetPayment[];
  stats: { payments_count: number; paid_total_rub: number; first_payment_at: string | null; last_payment_at: string | null };
  nodes: { name: string; country: string | null; online: boolean }[];
};

// GET /api/cabinet
export type CabinetData = { linked: boolean; demo: boolean; data: BotCabinet | null };

export type ApiError = { error: string; message: string };
