"use client";

import { useState } from "react";

export default function CallControls({
  disabled,
  sending,
  onSend,
}: {
  disabled: boolean;
  sending: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");

  const submit = () => {
    const value = text.trim();
    if (!value || disabled || sending) return;
    onSend(value);
    setText("");
  };

  return (
    <div className="flex gap-2">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Customer response..."
        disabled={disabled || sending}
        className="flex-1 rounded-lg border px-3 py-2 text-sm disabled:bg-gray-100"
      />
      <button
        onClick={submit}
        disabled={disabled || sending || !text.trim()}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:bg-gray-300"
      >
        {sending ? "Sending..." : "Send"}
      </button>
    </div>
  );
}
