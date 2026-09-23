import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Onest } from "next/font/google";
import "./globals.css";

const onest = Onest({
  subsets: ["latin", "cyrillic"],
  weight: ["100", "200", "300", "400"],
  variable: "--font-onest",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["200", "300", "400", "500"],
  variable: "--font-jbm",
  display: "swap",
});

export const metadata: Metadata = {
  title: "crs·vpn",
  description: "Частная сеть на своих серверах. Одна ссылка на все устройства.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#f6f8f7",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${onest.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
