import { notFound } from "next/navigation";
import LegalPage from "@/components/legal/LegalPage";
import { legalDocuments } from "@/lib/legal-documents";

export async function generateMetadata({ params }: { params: Promise<{ document: string }> }) {
  const { document } = await params;
  return { title: `${legalDocuments[document]?.title ?? "документ"} · crs·vpn`, robots: { index: false, follow: false } };
}

export default async function DocumentPage({ params }: { params: Promise<{ document: string }> }) {
  const { document } = await params;
  if (!Object.hasOwn(legalDocuments, document)) notFound();
  return <LegalPage document={legalDocuments[document]} />;
}
