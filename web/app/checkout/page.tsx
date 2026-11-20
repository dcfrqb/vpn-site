import AuthShell from "@/components/auth/AuthShell";
import Checkout from "@/components/checkout/Checkout";
import { requireAccount } from "@/lib/session";

export const metadata = { title: "оплата · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function CheckoutPage({ searchParams }: { searchParams: Promise<{ plan?: string; months?: string }> }) {
  const query = await searchParams;
  const plan = typeof query.plan === "string" ? query.plan : "";
  const months = Number(query.months);
  const path = `/checkout?plan=${encodeURIComponent(plan)}&months=${months}`;
  const account = await requireAccount(path);
  return <AuthShell signedIn={!!account} code="crs–01 · заказ" title="оплата" lede={<p>тариф и срок сохранятся после входа. подписка будет привязана к твоему аккаунту сайта.</p>}>
    {account ? <Checkout plan={plan} months={months} accountId={account.id} /> : <p className="form-err">не получилось загрузить аккаунт. обнови страницу.</p>}
  </AuthShell>;
}
