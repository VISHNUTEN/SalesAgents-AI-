"""Voice routes (Step 9: STT/TTS I/O around the SAME conversation core)."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.dependencies import ensure_not_completed, get_record_or_404
from app.api.routes.calls import _apply_action, process_customer_message
from app.api.schemas import AudioResponse, SpeakRequest
from app.models.call import CallSession
from app.services.voice.stt import STTError, get_stt_provider
from app.services.voice.tts import TTSError, get_tts_provider

router = APIRouter(prefix="/api/calls", tags=["voice"])


@router.post("/{call_id}/audio", response_model=AudioResponse)
async def receive_audio(call_id: str, file: UploadFile = File(...)):
    """Mic audio -> STT -> existing conversation core -> agent reply."""
    record = get_record_or_404(call_id)
    session: CallSession = record["session"]
    ensure_not_completed(session)
    audio = await file.read()
    try:
        transcript = await get_stt_provider().transcribe(
            audio, file.content_type or ""
        )
    except STTError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not transcript.strip():
        raise HTTPException(status_code=422, detail="No speech detected. Please try again.")
    action = process_customer_message(record, transcript)
    _apply_action(session, record, action)
    return AudioResponse(
        call_id=session.call_id,
        transcript=transcript,
        stage=action.stage.value,
        action=action.action.value,
        message=action.message,
        next_question=action.next_question,
        end_call=action.end_call,
        transfer_required=action.transfer_required,
        status=session.status.value,
    )


@router.post("/{call_id}/speak")
async def speak_text(call_id: str, request: SpeakRequest):
    """Agent text -> TTS audio. Never affects call state."""
    get_record_or_404(call_id)
    try:
        audio = await get_tts_provider().synthesize(request.text)
    except TTSError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return Response(content=audio, media_type="audio/wav")
