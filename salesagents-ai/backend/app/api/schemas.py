"""API request/response models (Step 7: transport only, no business rules)."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateCallRequest(BaseModel):
    customer_name: str = Field(min_length=1)
    agent_name: str = "Anjali"
    agent_gender: str = "female"
    company_name: str = "Home Credit"
    language_to_speak: str = "English"


class CallInfo(BaseModel):
    call_id: UUID
    customer_name: str
    customer_verified: bool
    status: str
    created_at: Any = None
    updated_at: Any = None


class AgentMessage(BaseModel):
    role: str
    content: str
    timestamp: Any = None


class StartCallResponse(BaseModel):
    call_id: UUID
    stage: str
    action: str
    message: str
    next_question: Optional[str] = None
    end_call: bool = False
    transfer_required: bool = False


class CustomerMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    extracted: Dict[str, Any] = Field(default_factory=dict)


class CustomerMessageResponse(BaseModel):
    call_id: UUID
    stage: str
    action: str
    message: str
    next_question: Optional[str] = None
    end_call: bool = False
    transfer_required: bool = False
    status: str


class CallDetailResponse(BaseModel):
    call_id: UUID
    customer_name: str
    customer_verified: bool
    status: str
    qualification: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    created_at: Any = None
    updated_at: Any = None


class AgentConfigResponse(BaseModel):
    agent_name: str
    agent_gender: str
    company_name: str


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class AudioResponse(BaseModel):
    call_id: UUID
    transcript: str
    stage: str
    action: str
    message: str
    next_question: Optional[str] = None
    end_call: bool = False
    transfer_required: bool = False
    status: str
