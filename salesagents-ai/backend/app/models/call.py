"""Call session and result models (Step 2: structural only)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .conversation import ConversationHistory
from .qualification import QualificationState


class CallStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISQUALIFIED = "disqualified"
    TRANSFERRED = "transferred"
    CALLBACK_REQUESTED = "callback_requested"


class CallSession(BaseModel):
    call_id: UUID = Field(default_factory=uuid4)
    customer_name: str = Field(min_length=1)
    customer_verified: bool = False
    status: CallStatus = CallStatus.INITIATED
    qualification: QualificationState = Field(default_factory=QualificationState)
    conversation_history: ConversationHistory = Field(default_factory=ConversationHistory)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CallResult(BaseModel):
    call_id: UUID
    status: CallStatus
    qualified: bool = False
    disqualified: bool = False
    transfer_required: bool = False
    reason: Optional[str] = None
    qualification: QualificationState = Field(default_factory=QualificationState)
