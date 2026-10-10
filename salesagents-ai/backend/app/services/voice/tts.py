"""Text-to-speech interface + provider selection (Step 9)."""

from abc import ABC, abstractmethod


class TTSError(Exception):
    """Synthesis failed."""


class TextToSpeech(ABC):
    media_type: str = "audio/wav"

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError


def get_tts_provider() -> TextToSpeech:
    """Mock by default so the app boots without API keys."""
    from app.core.config import settings
    from app.services.voice.providers.mock_tts import MockTTS

    name = (settings.TTS_PROVIDER or "mock").lower()
    if name == "mock":
        return MockTTS()
    raise TTSError(f"Unknown TTS provider: {name!r}")
