"use client";

import { useState } from "react";
import CallLogs from "../../components/CallLogs";
import QualificationState from "../../components/QualificationState";
import { getCall, type CallDetail } from "../../lib/api";

export default function CallsPage() {
  const [callId, setCallId] = useState("");
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function lookup() {
    if (!callId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setDetail(await getCall(callId.trim()));
    } catch (e) {
      setDetail(null);
      setError(e instanceof Error ? e.message : "Lookup failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <h1 className="text-2xl font-bold">Calls</h1>
      <p className="text-sm text-gray-600">
        MVP shows one active call at a time (no list endpoint yet). Paste a call ID to
        inspect it.
      </p>
      <div className="flex gap-2">
        <input
          value={callId}
          onChange={(e) => setCallId(e.target.value)}
          placeholder="Call ID"
          className="flex-1 rounded-lg border px-3 py-2 font-mono text-sm"
        />
        <button
          onClick={lookup}
          disabled={loading || !callId.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:bg-gray-300"
        >
          {loading ? "Loading..." : "Lookup"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {detail && (
        <>
          <CallLogs
            callId={detail.call_id}
            customerName={detail.customer_name}
            status={detail.status}
            verified={detail.customer_verified}
            messages={detail.conversation_history}
          />
          <QualificationState data={detail.qualification} />
        </>
      )}
    </main>
  );
}
