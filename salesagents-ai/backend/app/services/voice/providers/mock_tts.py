"""Mock TTS: synthesizes a short placeholder tone as WAV (stdlib only)."""

import io
import math
import struct
import wave

from app.services.voice.tts import TextToSpeech, TTSError

SAMPLE_RATE = 16000
DURATION_S = 0.4
FREQUENCY_HZ = 440.0


class MockTTS(TextToSpeech):
    media_type: str = "audio/wav"

    async def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            raise TTSError("Nothing to synthesize.")
        if len(text) > 2000:
            raise TTSError("Text too long.")
        try:
            frames = int(SAMPLE_RATE * DURATION_S)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                for i in range(frames):
                    sample = int(16000 * math.sin(2 * math.pi * FREQUENCY_HZ * i / SAMPLE_RATE))
                    wav.writeframes(struct.pack("<h", sample))
            return buf.getvalue()
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Synthesis failed: {exc}")
