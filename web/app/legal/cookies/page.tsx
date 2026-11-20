import LegalPage from "@/components/legal/LegalPage";
import { legalDocuments } from "@/lib/legal-documents";

export const metadata = { title: "cookie · crs·vpn" };
export default function CookiesPage() {
  return <LegalPage document={legalDocuments.cookies} />;
}
