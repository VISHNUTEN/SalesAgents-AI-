# Architecture — LAP Voice Agent (through Step 9)

## Text flow (source of truth, Steps 1–8)

```text
Frontend text input
  → POST /api/calls/{id}/message
  → calls.process_customer_message()   # single shared core
  → ConversationService → QualificationService → EligibilityService
  → ConversationAction → frontend
```

## Voice flow (Step 9: I/O only, no rule changes)

```text
Browser mic → MediaRecorder → POST /api/calls/{id}/audio (multipart)
  → STT provider → transcript text
  → calls.process_customer_message()   # SAME core as text
  → agent reply text → conversation UI
  → POST /api/calls/{id}/speak → TTS WAV → browser Audio() playback
```

Voice and text converge at `process_customer_message`, so both produce
identical qualification/eligibility results.

## Voice providers (`backend/app/services/voice/`)

- `stt.py` / `tts.py`: `SpeechToText` / `TextToSpeech` ABCs + `STTError` /
  `TTSError` + `get_*_provider()` factories.
- `providers/mock_stt.py`: deterministic mock (empty audio → `STTError`;
  `TRANSCRIPT:`-prefixed payloads are a test hook).
- `providers/mock_tts.py`: stdlib-only placeholder WAV tone.
- Selection via `STT_PROVIDER` / `TTS_PROVIDER` (default `mock`); the app
  boots with no API keys. Real providers implement the same ABCs later.

## Frontend (`frontend/`)

`CallConsole` owns call state; `VoiceControls` (MediaRecorder,
explicit start/stop) feeds Blobs to `sendAudio()`; agent replies play via
`synthesizeSpeech()` + `Audio()`. Text input always stays available.
Voice states: idle → recording → transcribing → processing → speaking → idle.
No provider keys in frontend (`NEXT_PUBLIC_*` carries only the API URL).
