"""Mock STT for the text MVP: deterministic, no network, no keys.

Test hook: audio payloads starting with b"TRANSCRIPT:" return the remainder
as the transcript so the full voice->conversation path is testable.
"""

from app.services.voice.stt import STTError, SpeechToText

MARKER = b"TRANSCRIPT:"
FALLBACK_TRANSCRIPT = "yes"


class MockSTT(SpeechToText):
    async def transcribe(self, audio_bytes: bytes, content_type: str = "") -> str:
        if not audio_bytes:
            raise STTError("No speech detected. Please try again.")
        if audio_bytes.startswith(MARKER):
            text = audio_bytes[len(MARKER):].decode("utf-8", errors="ignore").strip()
            if not text:
                raise STTError("No speech detected. Please try again.")
            return text
        return FALLBACK_TRANSCRIPT
