"""Speech-to-text interface + provider selection (Step 9)."""

from abc import ABC, abstractmethod


class STTError(Exception):
    """Transcription failed (empty audio, provider error, ...)."""


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, content_type: str = "") -> str:
        raise NotImplementedError


def get_stt_provider() -> SpeechToText:
    """Mock by default so the app boots without API keys."""
    from app.core.config import settings
    from app.services.voice.providers.mock_stt import MockSTT

    name = (settings.STT_PROVIDER or "mock").lower()
    if name == "mock":
        return MockSTT()
    raise STTError(f"Unknown STT provider: {name!r}")
