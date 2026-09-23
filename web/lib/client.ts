"use client";

export type CallResult<T> = { ok: true; status: number; data: T } | { ok: false; status: number; error: string; message: string };

function minutes(sec: number) {
  const m = Math.max(1, Math.ceil(sec / 60));
  return m === 1 ? "минуту" : m < 5 ? `${m} минуты` : `${m} минут`;
}

// Browser call to the api on the same origin. Never throws: errors come back as plain russian text.
export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<CallResult<T>> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: init.method ?? (init.body === undefined ? "GET" : "POST"),
      credentials: "same-origin",
      headers: init.body === undefined ? { accept: "application/json" } : { accept: "application/json", "content-type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    return { ok: false, status: 0, error: "network", message: "нет связи с сервером. проверь интернет и попробуй еще раз." };
  }

  let payload: unknown = null;
  if (res.status !== 204) {
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
  }

  if (res.ok) return { ok: true, status: res.status, data: payload as T };

  const p = (payload ?? {}) as { error?: string; message?: string; retry_after?: number };
  const retry = Number(res.headers.get("retry-after") ?? p.retry_after ?? 0);
  let message = typeof p.message === "string" && p.message ? p.message : "";
  if (!message) {
    if (res.status === 429) message = retry > 0 ? `слишком много попыток. попробуй через ${minutes(retry)}.` : "слишком много попыток. подожди немного.";
    else if (res.status === 401) message = "нужно войти заново.";
    else if (res.status === 403) message = "запрос отклонен. обнови страницу и попробуй еще раз.";
    else if (res.status >= 500) message = "что-то сломалось на нашей стороне. попробуй через пару минут.";
    else message = "не получилось. попробуй еще раз.";
  }
  return { ok: false, status: res.status, error: p.error ?? `http_${res.status}`, message };
}

// WebAuthn options may come flat ({...options, challenge_id}) or wrapped ({options|publicKey, challenge_id}).
export function splitOptions<O>(raw: Record<string, unknown>): { challengeId: string; options: O } {
  const { challenge_id, options, publicKey, ...rest } = raw as { challenge_id: string; options?: O; publicKey?: O };
  return { challengeId: challenge_id, options: (options ?? publicKey ?? (rest as O)) as O };
}

// User closed the passkey sheet or it timed out: not an error worth shouting about.
export function isPasskeyCancel(e: unknown): boolean {
  if (!e || typeof e !== "object") return false;
  const err = e as { name?: string; code?: string; cause?: { name?: string } };
  return (
    err.name === "NotAllowedError" ||
    err.name === "AbortError" ||
    err.code === "ERROR_CEREMONY_ABORTED" ||
    err.cause?.name === "NotAllowedError" ||
    err.cause?.name === "AbortError"
  );
}

export const PASSWORD_MIN = 10;
export const PASSWORD_MAX = 128;

export function checkPassword(pw: string, repeat: string | null, email?: string | null): string | null {
  if (pw.length < PASSWORD_MIN) return `пароль короче ${PASSWORD_MIN} символов.`;
  if (pw.length > PASSWORD_MAX) return `пароль длиннее ${PASSWORD_MAX} символов.`;
  if (email && pw.trim().toLowerCase() === email.trim().toLowerCase()) return "пароль не должен совпадать с email.";
  if (repeat !== null && pw !== repeat) return "пароли не совпадают.";
  return null;
}
