from fastapi import FastAPI

from app.api.routes import agent, calls, qualification

app = FastAPI(title="SalesAgents AI - LAP Voice Agent")


@app.get("/")
def root():
    return {"status": "ok", "service": "lap-voice-agent", "step": 7}


app.include_router(agent.router)
app.include_router(calls.router)
app.include_router(qualification.router)
