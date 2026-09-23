"use client";

import { useRef, useState } from "react";

export default function CopyLink({ url }: { url: string }) {
  const ref = useRef<HTMLElement>(null);
  const [toast, setToast] = useState<string | null>(null);

  const say = (t: string) => {
    setToast(t);
    window.setTimeout(() => setToast(null), 1800);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      say("ссылка скопирована");
    } catch {
      // Clipboard API is blocked (old browser, no permission): select the text for a manual copy.
      const r = document.createRange();
      if (ref.current) r.selectNodeContents(ref.current);
      const s = window.getSelection();
      s?.removeAllRanges();
      s?.addRange(r);
      say("выделено, скопируй вручную");
    }
  };

  return (
    <>
      <div className="link-box">
        <code ref={ref}>{url}</code>
        <button type="button" onClick={copy}>
          копировать
        </button>
      </div>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </>
  );
}
