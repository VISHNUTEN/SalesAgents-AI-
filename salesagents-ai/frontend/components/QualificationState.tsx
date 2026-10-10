import type { Qualification } from "../lib/api";

const FIELDS: { key: keyof Qualification; label: string }[] = [
  { key: "property_type", label: "Property Type" },
  { key: "ownership_status", label: "Ownership" },
  { key: "documents_available", label: "Original Documents" },
  { key: "loan_amount", label: "Loan Amount" },
  { key: "occupation", label: "Occupation" },
  { key: "income_mode", label: "Income Mode" },
  { key: "market_value", label: "Market Value" },
  { key: "tenure", label: "Tenure" },
];

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "Not collected";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString("en-IN");
  return String(value);
}

export default function QualificationState({ data }: { data: Qualification | null }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-500">Qualification State</h2>
      {!data && <p className="mt-2 text-sm text-gray-400">Loading…</p>}
      {data && (
        <dl className="mt-2 divide-y text-sm">
          {FIELDS.map(({ key, label }) => {
            const collected = data[key] !== null && data[key] !== undefined;
            return (
              <div key={key} className="flex items-center justify-between py-1.5">
                <dt className="text-gray-600">{label}</dt>
                <dd className={collected ? "font-medium" : "text-gray-400"}>
                  {collected ? "✓ " : "○ "}
                  {formatValue(data[key])}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </div>
  );
}
