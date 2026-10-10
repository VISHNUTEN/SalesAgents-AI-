from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, calls, qualification, voice
from app.core.config import settings

app = FastAPI(title="SalesAgents AI - LAP Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "lap-voice-agent", "step": 8}


app.include_router(agent.router)
app.include_router(calls.router)
app.include_router(qualification.router)
app.include_router(voice.router)
