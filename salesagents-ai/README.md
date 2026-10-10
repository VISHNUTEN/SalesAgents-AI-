# SalesAgents AI — LAP Voice Agent (through Step 9)

AI voice agent for Home Credit pre-approved Loan Against Property (LAP) offer.

## Start backend
```bash
cd salesagents-ai/backend
pip install -r ../requirements.txt
uvicorn app.main:app --reload
```
Backend: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`

## Start frontend
```bash
cd salesagents-ai/frontend
npm install
npm run dev
```
Frontend: `http://localhost:3000` (set `NEXT_PUBLIC_API_URL` in `.env`; see `frontend/.env.example`).

## Voice mode (Step 9, browser voice — not telephony)
1. Open the Agent dashboard, start a call.
2. Click **🎤 Start Recording**, allow microphone permission when asked.
3. Speak, then click stop. The transcript is sent to the existing
   `POST /api/calls/{id}/message` engine; the agent reply appears as text
   and plays back as audio. Text input keeps working at all times.
4. If playback fails you see “Voice playback unavailable” and continue in text.

## Environment variables
Backend (`salesagents-ai/.env.example`): `STT_PROVIDER` / `TTS_PROVIDER`
(default `mock`, boots with no keys), `STT_API_KEY` / `TTS_API_KEY` for future
real providers. Never commit real keys. Frontend needs no provider keys.

## Limitations
Browser microphone + mock STT/TTS only. No Twilio/SIP, phone calls,
WebSockets, streaming, barge-in, or stored recordings — those come later.
Business rules live in backend services; voice is input/output only.
