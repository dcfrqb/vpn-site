import "server-only";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { Account, CabinetData, SessionInfo } from "./types";

const API = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8040";

type Result<T> = { state: "ok"; data: T } | { state: "anon" } | { state: "down"; status: number };

// Server-side call to the api with the visitor's cookie forwarded.
async function authed<T>(path: string): Promise<Result<T>> {
  const cookie = (await headers()).get("cookie");
  try {
    const res = await fetch(`${API}${path}`, {
      cache: "no-store",
      headers: cookie ? { cookie, accept: "application/json" } : { accept: "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    if (res.status === 401) return { state: "anon" };
    if (!res.ok) return { state: "down", status: res.status };
    return { state: "ok", data: (await res.json()) as T };
  } catch {
    return { state: "down", status: 0 };
  }
}

type MeResponse = { account: Account };

export async function getMe(): Promise<Result<Account>> {
  const r = await authed<MeResponse>("/api/me");
  return r.state === "ok" ? { state: "ok", data: r.data.account } : r;
}

// Guard for /cabinet*: 401 sends the visitor to /login with a way back.
export async function requireAccount(path: string): Promise<Account | null> {
  const me = await getMe();
  if (me.state === "anon") redirect(`/login?next=${encodeURIComponent(path)}`);
  return me.state === "ok" ? me.data : null;
}

// For /login and /register: a visitor with a live session goes straight on.
export async function redirectIfSignedIn(to: string): Promise<void> {
  const me = await getMe();
  if (me.state === "ok") redirect(to);
}

// 503 here means the api is up but the bot did not answer (error bot_unavailable).
export const getCabinet = () => authed<CabinetData>("/api/cabinet");
export const getSessions = () => authed<SessionInfo[]>("/api/me/sessions");
