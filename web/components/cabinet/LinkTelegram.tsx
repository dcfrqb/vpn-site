"use client";

import { useCallback } from "react";
import TelegramLogin from "@/components/auth/TelegramLogin";

// Linking from the cabinet: after success reload so the server fetches the bot data.
export default function LinkTelegram() {
  const done = useCallback(() => window.location.reload(), []);
  return <TelegramLogin mode="link" onDone={done} />;
}
