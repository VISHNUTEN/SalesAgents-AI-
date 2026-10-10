import CallConsole from "../../components/CallConsole";

export default function TestPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="mb-1 text-2xl font-bold">Test Conversation</h1>
      <p className="mb-4 text-sm text-gray-600">
        Start a call, send customer replies as text, and watch qualification state update.
      </p>
      <CallConsole showExtractor />
    </main>
  );
}
