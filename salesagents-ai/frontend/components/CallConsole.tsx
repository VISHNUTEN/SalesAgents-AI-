"use client";

import { useRef, useState } from "react";
import {
  createCall,
  getAgentConfig,
  getCall,
  sendAudio,
  sendMessage,
  startCall,
  synthesizeSpeech,
  type AgentConfig,
  type ChatMessage,
  type Qualification,
  type VoiceState,
} from "../lib/api";
import AgentPanel from "./AgentPanel";
import CallControls from "./CallControls";
import CallLogs from "./CallLogs";
import Conversation from "./Conversation";
import EligibilityStatus from "./EligibilityStatus";
import QualificationState from "./QualificationState";
import VoiceControls from "./VoiceControls";

const TERMINAL = ["completed", "disqualified", "transferred", "callback_requested"];

const QUICK_REPLIES = [
  "Yes, this is me.",
  "Yes, tell me more.",
  "I already have a property loan.",
  "I need 90 lakhs.",
];

export default function CallConsole({ showExtractor = false }: { showExtractor?: boolean }) {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [customerName, setCustomerName] = useState("Rahul");
  const [callId, setCallId] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [verified, setVerified] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [qualification, setQualification] = useState<Qualification | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [lastReason, setLastReason] = useState<string | null>(null);
  const [extractedJson, setExtractedJson] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voice, setVoice] = useState<VoiceState>("idle");
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const ended = TERMINAL.includes(status);
  const voiceActive = voice !== "idle" && voice !== "error";

  async function sync(call_id: string) {
    const detail = await getCall(call_id);
    setStatus(detail.status);
    setVerified(detail.customer_verified);
    setQualification(detail.qualification);
    setMessages(detail.conversation_history);
  }

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      const cfg = config ?? (await getAgentConfig());
      setConfig(cfg);
      const created = await createCall({
        customer_name: customerName.trim() || "Customer",
        agent_name: cfg.agent_name,
        agent_gender: cfg.agent_gender,
        company_name: cfg.company_name,
      });
      setCallId(created.call_id);
      const reply = await startCall(created.call_id);
      setLastAction(reply.action);
      await sync(created.call_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start call.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(text: string) {
    if (!callId) return;
    setBusy(true);
    setError(null);
    try {
      let extracted: Record<string, unknown> | undefined;
      if (showExtractor && extractedJson.trim()) {
        try {
          extracted = JSON.parse(extractedJson) as Record<string, unknown>;
        } catch {
          throw new Error("Extracted JSON is invalid. Fix it or clear the field.");
        }
      }
      const reply = await sendMessage(callId, text, extracted);
      setLastAction(reply.action);
      if (reply.action === "disqualify" || reply.action === "transfer") {
        setLastReason(reply.message);
      }
      if (showExtractor) setExtractedJson("");
      await sync(callId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send message.");
    } finally {
      setBusy(false);
    }
  }

  async function playReply(call_id: string, text: string) {
    setVoice("speaking");
    try {
      const blob = await synthesizeSpeech(call_id, text);
      const url = URL.createObjectURL(blob);
      await new Promise<void>((resolve) => {
        const el = new Audio(url);
        audioRef.current = el;
        el.onended = () => {
          URL.revokeObjectURL(url);
          resolve();
        };
        el.onerror = () => {
          URL.revokeObjectURL(url);
          resolve();
        };
        el.play().catch(() => resolve());
      });
    } catch (e) {
      setVoiceNote(e instanceof Error ? e.message : "Voice playback unavailable.");
    } finally {
      audioRef.current = null;
      setVoice("idle");
    }
  }

  async function handleAudio(blob: Blob) {
    if (!callId) return;
    setBusy(true);
    setError(null);
    setVoiceNote(null);
    try {
      setVoice("transcribing");
      const reply = await sendAudio(callId, blob);
      setVoice("processing");
      setLastAction(reply.action);
      if (reply.action === "disqualify" || reply.action === "transfer") {
        setLastReason(reply.message);
      }
      await sync(callId);
      await playReply(callId, reply.message);
    } catch (e) {
      setVoice("error");
      setError(e instanceof Error ? e.message : "Voice request failed.");
    } finally {
      setBusy(false);
      setVoice("idle");
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="Customer name"
              disabled={busy || callId !== null}
              className="w-48 rounded-lg border px-3 py-2 text-sm disabled:bg-gray-100"
            />
            <button
              onClick={handleStart}
              disabled={busy || callId !== null}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white disabled:bg-gray-300"
            >
              {busy && !callId ? "Starting call..." : "Start Call"}
            </button>
            {callId && (
              <span className="text-sm text-gray-600">
                Status: <span className="font-medium">{status}</span>
              </span>
            )}
          </div>
          {showExtractor && (
            <div className="mt-3 flex flex-wrap gap-2">
              {QUICK_REPLIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  disabled={!callId || ended || busy}
                  className="rounded-full border px-3 py-1 text-xs text-gray-700 disabled:opacity-40"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>

        <Conversation messages={messages} />

        {showExtractor && (
          <details className="rounded-lg border bg-white p-4">
            <summary className="cursor-pointer text-sm font-medium text-gray-700">
              Dev harness: structured slots (stands in for the Step-9 LLM extractor)
            </summary>
            <textarea
              value={extractedJson}
              onChange={(e) => setExtractedJson(e.target.value)}
              placeholder='e.g. {"property_type": "residential", "tenure": 10}'
              rows={3}
              className="mt-2 w-full rounded-lg border p-2 font-mono text-xs"
            />
          </details>
        )}

        <CallControls disabled={!callId || ended} sending={busy} onSend={handleSend} />
        <div className="flex items-center gap-3">
          <VoiceControls disabled={!callId || ended || busy} onAudio={handleAudio} />
          {voiceActive && (
            <span className="text-xs font-medium text-gray-600">
              {voice === "recording" && "● Recording"}
              {voice === "transcribing" && "⏳ Transcribing..."}
              {voice === "processing" && "⏳ Processing..."}
              {voice === "speaking" && "🔊 Speaking..."}
            </span>
          )}
        </div>
        {voiceNote && <p className="text-xs text-amber-700">{voiceNote}</p>}
        {ended && (
          <p className="text-sm font-medium text-gray-700">
            Call ended ({status}). Start a new call to continue testing.
          </p>
        )}
      </div>

      <div className="space-y-4">
        <AgentPanel config={config} />
        <EligibilityStatus lastAction={lastAction} reason={lastReason} />
        <QualificationState data={qualification} />
        <CallLogs
          callId={callId}
          customerName={customerName}
          status={status}
          verified={verified}
          messages={messages}
        />
      </div>
    </div>
  );
}
