"""Voice endpoint tests: audio->STT->same core, TTS audio/fallback (no telephony)."""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import CALL_SESSIONS
from app.main import app
from app.services.voice import stt as stt_module
from app.services.voice import tts as tts_module
from app.services.voice.providers.mock_stt import MockSTT
from app.services.voice.stt import STTError
from app.services.voice.tts import TTSError

client = TestClient(app)


def _started_call():
    CALL_SESSIONS.clear()
    call_id = client.post("/api/calls", json={"customer_name": "Rahul"}).json()["call_id"]
    client.post(f"/api/calls/{call_id}/start")
    return call_id


def _audio(transcript: str):
    return {"file": ("mic.webm", b"TRANSCRIPT:" + transcript.encode(), "audio/webm")}


def test_audio_unknown_call_404():
    r = client.post(
        "/api/calls/00000000-0000-0000-0000-000000000000/audio", files=_audio("yes")
    )
    assert r.status_code == 404


def test_audio_empty_recording_422():
    call_id = _started_call()
    r = client.post(
        "/api/calls/{}/audio".format(call_id),
        files={"file": ("mic.webm", b"", "audio/webm")},
    )
    assert r.status_code == 422


def test_stt_called_and_text_flows_to_core(monkeypatch):
    calls = []

    class SpySTT(MockSTT):
        async def transcribe(self, audio_bytes, content_type=""):
            calls.append(audio_bytes)
            return await super().transcribe(audio_bytes, content_type)

    monkeypatch.setattr(stt_module, "get_stt_provider", lambda: SpySTT())
    import app.api.routes.voice as voice_route

    monkeypatch.setattr(voice_route, "get_stt_provider", lambda: SpySTT())
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/audio", files=_audio("Yes, this is Rahul."))
    body = r.json()
    assert r.status_code == 200
    assert calls and body["transcript"] == "Yes, this is Rahul."
    assert body["stage"] == "offer"  # same verification result as text mode


def test_voice_obeys_business_rules():
    call_id = _started_call()
    client.post(f"/api/calls/{call_id}/audio", files=_audio("Yes, this is Rahul."))
    client.post(f"/api/calls/{call_id}/audio", files=_audio("Yes."))
    body = client.post(
        f"/api/calls/{call_id}/audio", files=_audio("agricultural land")
    ).json()
    assert body["action"] == "disqualify"
    q = client.get(f"/api/calls/{call_id}/qualification").json()
    assert q["property_type"] == "agricultural"


def test_speak_returns_audio():
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/speak", json={"text": "Hello Rahul."})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF"


def test_speak_unknown_call_404():
    r = client.post(
        "/api/calls/00000000-0000-0000-0000-000000000000/speak", json={"text": "Hi."}
    )
    assert r.status_code == 404


def test_tts_failure_keeps_conversation(monkeypatch):
    class BrokenTTS:
        media_type = "audio/wav"

        async def synthesize(self, text):
            raise TTSError("provider down")

    import app.api.routes.voice as voice_route

    monkeypatch.setattr(voice_route, "get_tts_provider", lambda: BrokenTTS())
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/speak", json={"text": "Hello."})
    assert r.status_code == 503
    # Conversation still works via text.
    r2 = client.post(f"/api/calls/{call_id}/message", json={"message": "Yes, this is Rahul."})
    assert r2.status_code == 200
    assert r2.json()["stage"] == "offer"


def test_stt_failure_returns_friendly_422(monkeypatch):
    class BrokenSTT:
        async def transcribe(self, audio_bytes, content_type=""):
            raise STTError("We couldn't understand the audio. Please try again.")

    import app.api.routes.voice as voice_route

    monkeypatch.setattr(voice_route, "get_stt_provider", lambda: BrokenSTT())
    call_id = _started_call()
    r = client.post(f"/api/calls/{call_id}/audio", files=_audio("whatever"))
    assert r.status_code == 422
    assert "understand" in r.json()["detail"]
