/** Centralized FastAPI client. No raw fetch() elsewhere. No business rules here. */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AgentConfig {
  agent_name: string;
  agent_gender: string;
  company_name: string;
}

export interface Qualification {
  customer_verified?: boolean | null;
  property_type: string | null;
  ownership_status: string | null;
  documents_available: boolean | null;
  loan_amount: number | string | null;
  occupation: string | null;
  income_mode: string | null;
  market_value: number | string | null;
  tenure: number | null;
  existing_property_loan?: boolean | null;
  emi_reduction_request?: boolean | null;
  disqualified?: boolean;
  transfer_required?: boolean;
}

export interface ChatMessage {
  role: string;
  content: string;
  timestamp?: string;
}

export interface CallDetail {
  call_id: string;
  customer_name: string;
  customer_verified: boolean;
  status: string;
  qualification: Qualification;
  conversation_history: ChatMessage[];
}

export interface AgentReply {
  call_id: string;
  stage: string;
  action: string;
  message: string;
  next_question: string | null;
  end_call: boolean;
  transfer_required: boolean;
  status?: string;
}

export interface AudioReply extends AgentReply {
  transcript: string;
}

export type VoiceState =
  | "idle"
  | "recording"
  | "transcribing"
  | "processing"
  | "speaking"
  | "error";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(
      "Unable to connect to the backend. Please check that the FastAPI server is running."
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const msg =
      typeof detail?.detail === "string" ? detail.detail : `Request failed (${res.status}).`;
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export function getAgentConfig(): Promise<AgentConfig> {
  return request<AgentConfig>("/api/agent/config");
}

export function createCall(input: {
  customer_name: string;
  agent_name: string;
  agent_gender: string;
  company_name: string;
  language_to_speak?: string;
}): Promise<{ call_id: string; status: string; customer_name: string }> {
  return request("/api/calls", {
    method: "POST",
    body: JSON.stringify({ language_to_speak: "English", ...input }),
  });
}

export function startCall(callId: string): Promise<AgentReply> {
  return request<AgentReply>(`/api/calls/${callId}/start`, { method: "POST" });
}

export function sendMessage(
  callId: string,
  message: string,
  extracted?: Record<string, unknown>
): Promise<AgentReply> {
  return request<AgentReply>(`/api/calls/${callId}/message`, {
    method: "POST",
    body: JSON.stringify({ message, extracted: extracted ?? {} }),
  });
}

export function getCall(callId: string): Promise<CallDetail> {
  return request<CallDetail>(`/api/calls/${callId}`);
}

export function getQualification(callId: string): Promise<Qualification> {
  return request<Qualification>(`/api/calls/${callId}/qualification`);
}

export async function sendAudio(callId: string, audio: Blob): Promise<AudioReply> {
  const form = new FormData();
  form.append("file", audio, "mic.webm");
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/calls/${callId}/audio`, { method: "POST", body: form });
  } catch {
    throw new Error(
      "Unable to connect to the backend. Please check that the FastAPI server is running."
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const msg =
      typeof detail?.detail === "string" ? detail.detail : `Voice request failed (${res.status}).`;
    throw new Error(msg);
  }
  return (await res.json()) as AudioReply;
}

export async function synthesizeSpeech(callId: string, text: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/calls/${callId}/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new Error("Voice playback unavailable. You can continue using text.");
  }
  if (!res.ok) throw new Error("Voice playback unavailable. You can continue using text.");
  return await res.blob();
}
