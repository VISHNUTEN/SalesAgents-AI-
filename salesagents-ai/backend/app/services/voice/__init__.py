"""Voice provider interfaces (Step 9: STT/TTS boundaries, no telephony)."""

from app.services.voice.stt import STTError, SpeechToText, get_stt_provider
from app.services.voice.tts import TTSError, TextToSpeech, get_tts_provider

__all__ = [
    "SpeechToText",
    "STTError",
    "get_stt_provider",
    "TextToSpeech",
    "TTSError",
    "get_tts_provider",
]
