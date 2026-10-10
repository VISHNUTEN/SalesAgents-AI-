"""Qualification-state route (Step 7: read-only view, no business rules)."""

from typing import Any, Dict

from fastapi import APIRouter

from app.api.dependencies import get_record_or_404

router = APIRouter(prefix="/api/calls", tags=["qualification"])


@router.get("/{call_id}/qualification", response_model=Dict[str, Any])
def get_qualification(call_id: str) -> Dict[str, Any]:
    record = get_record_or_404(call_id)
    return record["session"].qualification.model_dump(mode="json")
