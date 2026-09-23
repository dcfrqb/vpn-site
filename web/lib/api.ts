import "server-only";

export type Plan = {
  code: string;
  title: string;
  device_limit: number;
  countries: string[];
  prices: Record<string, number>;
  ru_entry_gb: number | null;
  highlighted: boolean;
};

export type NetworkStatus = {
  nodes_total: number;
  nodes_online: number;
  exit_countries: string[];
  nodes: { name: string; country: string; online: boolean }[];
};

const API = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8040";

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const getPlans = () => get<Plan[]>("/api/plans");
export const getNetwork = () => get<NetworkStatus>("/api/network");
