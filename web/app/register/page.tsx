import { redirect } from "next/navigation";
import { safeNext } from "@/lib/next-path";

// Registration lives in the single email form on /login.
export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const next = safeNext((await searchParams).next);
  redirect(next === "/cabinet" ? "/login" : `/login?next=${encodeURIComponent(next)}`);
}
