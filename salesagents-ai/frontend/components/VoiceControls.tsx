"use client";

import { useRef, useState } from "react";

export default function VoiceControls({
  disabled,
  onAudio,
}: {
  disabled: boolean;
  onAudio: (audio: Blob) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  async function start() {
    setError(null);
    if (!supported) {
      setError("Voice input is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (blob.size === 0) {
          setError("No speech detected. Please try again.");
        } else {
          onAudio(blob);
        }
      };
      recorder.onerror = () => setError("We couldn't record audio. Please try again.");
      recorder.start();
      setRecording(true);
    } catch {
      setError("Microphone permission is required for voice input.");
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        {!recording ? (
          <button
            onClick={start}
            disabled={disabled}
            title="Start recording"
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
          >
            🎤 Start Recording
          </button>
        ) : (
          <button
            onClick={stop}
            className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white"
          >
            🔴 Recording… (click to stop)
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
