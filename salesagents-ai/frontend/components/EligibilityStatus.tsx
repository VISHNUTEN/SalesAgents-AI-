/** Presentation only: maps the backend's last action to a status label. */

const LABELS: Record<string, { text: string; classes: string }> = {
  qualify: { text: "Qualified", classes: "bg-green-100 text-green-800" },
  disqualify: { text: "Disqualified", classes: "bg-red-100 text-red-800" },
  transfer: { text: "Transfer Required", classes: "bg-amber-100 text-amber-800" },
};

export default function EligibilityStatus({
  lastAction,
  reason,
}: {
  lastAction: string | null;
  reason: string | null;
}) {
  const entry =
    lastAction !== null && lastAction in LABELS
      ? LABELS[lastAction]
      : { text: "Pending", classes: "bg-gray-100 text-gray-700" };
  return (
    <div className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-500">Eligibility Status</h2>
      <span
        className={`mt-2 inline-block rounded-full px-3 py-1 text-sm font-medium ${entry.classes}`}
      >
        {entry.text.toUpperCase()}
      </span>
      {lastAction === "disqualify" && reason && (
        <p className="mt-2 text-sm text-gray-700">
          <span className="font-medium">Reason: </span>
          {reason}
        </p>
      )}
      {lastAction === "transfer" && (
        <p className="mt-2 text-sm text-gray-700">
          Routed to the loan-transfer specialist.
        </p>
      )}
    </div>
  );
}
