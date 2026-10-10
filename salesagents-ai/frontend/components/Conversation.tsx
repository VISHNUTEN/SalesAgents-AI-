"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "../lib/api";

export default function Conversation({ messages }: { messages: ChatMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="flex h-96 flex-col gap-3 overflow-y-auto rounded-lg border bg-white p-4">
      {messages.length === 0 && (
        <p className="text-sm text-gray-400">No messages yet. Start a call.</p>
      )}
      {messages.map((m, i) => {
        const isAgent = m.role !== "user";
        return (
          <div key={i} className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                isAgent ? "bg-gray-100 text-gray-900" : "bg-blue-600 text-white"
              }`}
            >
              <p className="mb-1 text-[11px] font-semibold tracking-wide opacity-70">
                {isAgent ? "AGENT" : "CUSTOMER"}
              </p>
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
