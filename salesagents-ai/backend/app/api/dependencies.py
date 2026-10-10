"""Shared API dependencies (Step 7: in-memory session store).

MVP only: a dict that a database can replace later.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from fastapi import HTTPException

from app.models.call import CallSession

# call_id string -> record with session + runtime config/stage.
CALL_SESSIONS: Dict[str, Dict[str, Any]] = {}

TERMINAL_STATUSES = {"completed", "disqualified", "transferred", "callback_requested"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_record_or_404(call_id: str) -> Dict[str, Any]:
    record = CALL_SESSIONS.get(str(call_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return record


def get_session_or_404(call_id: str) -> CallSession:
    return get_record_or_404(call_id)["session"]


def ensure_not_completed(session: CallSession) -> None:
    if session.status.value in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Call already completed")


def try_uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError:
        raise HTTPException(status_code=404, detail="Call not found")
