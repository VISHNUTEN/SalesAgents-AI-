import type { AgentConfig } from "../lib/api";

export default function AgentPanel({ config }: { config: AgentConfig | null }) {
  if (!config) return <p className="text-sm text-gray-500">Loading agent…</p>;
  return (
    <div className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-500">Agent</h2>
      <p className="mt-1 text-lg font-medium">{config.agent_name}</p>
      <p className="text-sm text-gray-600">
        {config.company_name} · {config.agent_gender}
      </p>
    </div>
  );
}
