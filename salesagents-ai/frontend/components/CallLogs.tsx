import type { ChatMessage } from "../lib/api";

export default function CallLogs({
  callId,
  customerName,
  status,
  verified,
  messages,
}: {
  callId: string | null;
  customerName: string;
  status: string;
  verified: boolean;
  messages: ChatMessage[];
}) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-500">Call Logs</h2>
      {!callId ? (
        <p className="mt-2 text-sm text-gray-400">No call yet.</p>
      ) : (
        <div className="mt-2 space-y-1 text-sm">
          <p>
            <span className="text-gray-500">Call ID: </span>
            <span className="font-mono text-xs">{callId}</span>
          </p>
          <p>
            <span className="text-gray-500">Customer: </span>
            {customerName} {verified ? "(verified)" : "(unverified)"}
          </p>
          <p>
            <span className="text-gray-500">Status: </span>
            <span className="font-medium">{status}</span>
          </p>
          <p>
            <span className="text-gray-500">Turns: </span>
            {messages.length}
          </p>
        </div>
      )}
    </div>
  );
}
