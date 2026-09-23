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

export type CabinetData = {
  linked: boolean;
  subscription: {
    plan: string;
    status: string;
    valid_until: string;
    days_left: number;
    device_limit: number;
    sub_url: string;
    traffic_month_gb: number;
  } | null;
  devices: { name: string; last_seen_at: string | null }[];
  payments: { date: string; plan: string; months: number; amount_rub: number; status: string }[];
  nodes: { name: string; country: string; online: boolean; ping_ms: number | null }[];
  demo: boolean;
};

export type ApiError = { error: string; message: string };
