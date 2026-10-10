"""Conversation message models (Steps 2 + 5: structural only, no LLM)."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationHistory(BaseModel):
    messages: List[ConversationMessage] = Field(default_factory=list)


class ConversationStage(str, Enum):
    GREETING = "greeting"
    VERIFICATION = "verification"
    OFFER = "offer"
    QUALIFICATION = "qualification"
    CALLBACK = "callback"
    TRANSFER = "transfer"
    DISQUALIFIED = "disqualified"
    QUALIFIED = "qualified"
    COMPLETED = "completed"


class ConversationActionType(str, Enum):
    GREETING = "greeting"
    VERIFY_CUSTOMER = "verify_customer"
    PRESENT_OFFER = "present_offer"
    ASK_QUESTION = "ask_question"
    HANDLE_RESPONSE = "handle_response"
    REQUEST_CALLBACK = "request_callback"
    TRANSFER = "transfer"
    DISQUALIFY = "disqualify"
    QUALIFY = "qualify"
    END_CALL = "end_call"


class ConversationAction(BaseModel):
    stage: ConversationStage
    action: ConversationActionType
    message: str = Field(min_length=1)
    next_question: Optional[str] = None
    end_call: bool = False
    transfer_required: bool = False
