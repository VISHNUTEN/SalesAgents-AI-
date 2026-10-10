import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-center">
      <h1 className="text-3xl font-bold">SalesAgents AI</h1>
      <p className="mt-2 text-gray-600">AI Voice Agent — Loan Against Property</p>
      <div className="mt-8 flex justify-center gap-3">
        <Link
          href="/agent"
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white"
        >
          Open Agent
        </Link>
        <Link
          href="/test"
          className="rounded-lg border px-5 py-2.5 text-sm font-medium text-gray-700"
        >
          Test Conversation
        </Link>
      </div>
    </main>
  );
}
