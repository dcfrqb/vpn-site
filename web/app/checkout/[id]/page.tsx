import AuthShell from "@/components/auth/AuthShell";
import OrderStatus from "@/components/checkout/OrderStatus";
import { requireAccount } from "@/lib/session";

export const metadata = { title: "заказ · crs·vpn" };
export const dynamic = "force-dynamic";

export default async function OrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const account = await requireAccount(`/checkout/${encodeURIComponent(id)}`);
  return <AuthShell signedIn={!!account} code="crs–01 · заказ" title="твой заказ" lede={<p>проверяем оплату и выдачу подписки. страницу можно закрыть и открыть позже, заказ сохранится.</p>}>
    {account ? <OrderStatus id={id} /> : <p className="form-err">не получилось загрузить аккаунт. обнови страницу.</p>}
  </AuthShell>;
}
