import type { Metadata, Viewport } from "next";
// Fonts ship with the app (no build-time or runtime requests to Google).
import "@fontsource-variable/onest";
import "@fontsource-variable/jetbrains-mono";
import "./globals.css";

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
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
