# SalesAgents AI — LAP Voice Agent (Step 1: Project Structure)

AI voice agent for Home Credit pre-approved Loan Against Property (LAP) offer.

## Architecture (target)
- `frontend/` — Next.js UI (voice interface, transcript, state, logs, test scenarios).
- `backend/` — Python + FastAPI (conversation, qualification state, eligibility engine, handoff, transcript logging, RAG, system prompt).
- `docs/` — architecture, test scenarios, approach.
- `backend/tests/` — eligibility, conversation, edge-case tests.

## Start backend
```bash
cd salesagents-ai/backend
pip install -r ../requirements.txt
uvicorn app.main:app --reload
```
Verify: `GET http://127.0.0.1:8000/` → HTTP 200 `{"status":"ok",...}`.

## Start frontend
Not implemented yet (Step 1 = structure only). Future: `cd salesagents-ai/frontend && npm install && npm run dev`.

## Status
Step 1 complete: skeleton + health endpoint only. No models, rules, voice, or prompt logic yet.
