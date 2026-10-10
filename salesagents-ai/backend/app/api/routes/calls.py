"""Call session routes (Step 7: thin orchestration, no business rules)."""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.api.dependencies import (
    CALL_SESSIONS,
    ensure_not_completed,
    get_record_or_404,
    utcnow,
)
from app.api.schemas import (
    CallDetailResponse,
    CallInfo,
    CreateCallRequest,
    CustomerMessageRequest,
    CustomerMessageResponse,
    StartCallResponse,
)
from app.core.config import settings
from app.models.call import CallSession, CallStatus
from app.models.conversation import ConversationAction, MessageRole
from app.models.qualification import QualificationState
from app.services.conversation_service import ConversationService
from app.services import prompt_service, response_extractor
from app.services.eligibility_service import MAX_LOAN_AMOUNT

router = APIRouter(prefix="/api/calls", tags=["calls"])


def _apply_auto_extract(session: CallSession, svc: ConversationService, text: str) -> None:
    """Fold natural-language slots into state; never raises."""
    try:
        auto = response_extractor.extract(text)
    except Exception:
        return
    if not auto:
        return
    try:
        updated = svc.qualification.update_state(session.qualification, auto)
    except Exception:
        return
    for field in type(session.qualification).model_fields:
        setattr(session.qualification, field, getattr(updated, field))


def _append(session: CallSession, role: MessageRole, content: str) -> None:
    from app.models.conversation import ConversationMessage

    session.conversation_history.messages.append(
        ConversationMessage(role=role, content=content)
    )
    session.updated_at = utcnow()


def _service_for(record) -> ConversationService:
    return record["service"]


def _sync_verified(session: CallSession) -> None:
    if session.qualification.customer_verified:
        session.customer_verified = True


def _apply_action(session: CallSession, record, action: ConversationAction) -> None:
    from app.models.conversation import ConversationActionType

    _sync_verified(session)
    if action.action == ConversationActionType.TRANSFER:
        session.status = CallStatus.TRANSFERRED
    elif action.action == ConversationActionType.DISQUALIFY:
        session.status = CallStatus.DISQUALIFIED
    elif action.action == ConversationActionType.QUALIFY:
        session.status = CallStatus.COMPLETED
    elif action.action == ConversationActionType.REQUEST_CALLBACK:
        session.status = CallStatus.CALLBACK_REQUESTED
    elif action.end_call:
        session.status = CallStatus.COMPLETED
    else:
        session.status = CallStatus.IN_PROGRESS
    _append(session, MessageRole.ASSISTANT, action.message)


def _prompt_boundary(record, utterance: str) -> None:
    """Step-9 integration boundary: build render context, no LLM call."""
    session = record["session"]
    history = "\n".join(
        f"{m.role.value}: {m.content}"
        for m in session.conversation_history.messages[-10:]
    )
    now: datetime = utcnow()
    context = {
        "company_name": record["company_name"],
        "customer_name": session.customer_name,
        "agent_name": record["agent_name"],
        "agent_gender": record["agent_gender"],
        "current_date": now.date().isoformat(),
        "current_day": now.strftime("%A"),
        "current_time": now.strftime("%H:%M"),
        "additional_context_from_rag": "",
        "language_to_speak": record["language"],
        "conversation_history": history,
        "customer_utterance": utterance,
    }
    record["last_prompt_context"] = context
    try:
        prompt_service.render_prompt(context)
    except Exception:
        pass


def _to_response(session: CallSession, action: ConversationAction, response_model):
    return response_model(
        call_id=session.call_id,
        stage=action.stage.value,
        action=action.action.value,
        message=action.message,
        next_question=action.next_question,
        end_call=action.end_call,
        transfer_required=action.transfer_required,
        **({"status": session.status.value} if "status" in response_model.model_fields else {}),
    )


@router.post("", response_model=CallInfo, status_code=201)
def create_call(request: CreateCallRequest) -> CallInfo:
    agent_name = request.agent_name or settings.AGENT_NAME
    session = CallSession(
        customer_name=request.customer_name,
        status=CallStatus.INITIATED,
        qualification=QualificationState(),
    )
    CALL_SESSIONS[str(session.call_id)] = {
        "session": session,
        "agent_name": agent_name,
        "agent_gender": request.agent_gender or settings.AGENT_GENDER,
        "company_name": request.company_name or settings.COMPANY_NAME,
        "language": request.language_to_speak or "English",
        "stage": "new",
        "downgrade_pending": False,
        "service": ConversationService(
            company_name=request.company_name or settings.COMPANY_NAME,
            agent_name=agent_name,
        ),
    }
    return CallInfo(
        call_id=session.call_id,
        customer_name=session.customer_name,
        customer_verified=session.customer_verified,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/{call_id}", response_model=CallDetailResponse)
def get_call(call_id: str) -> CallDetailResponse:
    record = get_record_or_404(call_id)
    session: CallSession = record["session"]
    return CallDetailResponse(
        call_id=session.call_id,
        customer_name=session.customer_name,
        customer_verified=session.customer_verified,
        status=session.status.value,
        qualification=session.qualification.model_dump(mode="json"),
        conversation_history=[
            {"role": m.role.value, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in session.conversation_history.messages
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/{call_id}/start", response_model=StartCallResponse)
def start_call(call_id: str) -> StartCallResponse:
    from fastapi import HTTPException

    record = get_record_or_404(call_id)
    session: CallSession = record["session"]
    if session.status != CallStatus.INITIATED:
        raise HTTPException(status_code=409, detail="Call already started or completed")
    session.status = CallStatus.IN_PROGRESS
    record["stage"] = "verification"
    action = _service_for(record).greet(session.customer_name)
    _append(session, MessageRole.ASSISTANT, action.message)
    return StartCallResponse(
        call_id=session.call_id,
        stage=action.stage.value,
        action=action.action.value,
        message=action.message,
        next_question=action.next_question,
        end_call=action.end_call,
        transfer_required=action.transfer_required,
    )


@router.post("/{call_id}/message", response_model=CustomerMessageResponse)
def customer_message(call_id: str, request: CustomerMessageRequest):
    record = get_record_or_404(call_id)
    session: CallSession = record["session"]
    ensure_not_completed(session)
    action = process_customer_message(record, request.message, request.extracted)
    _apply_action(session, record, action)
    return _to_response(session, action, CustomerMessageResponse)


def process_customer_message(record, text: str, extracted: Optional[Dict[str, Any]] = None):
    """Shared text/voice core: user text -> stage machine -> next action.

    Both the text endpoint and the audio (STT) endpoint MUST use this so
    voice and text produce identical business results.
    """
    session: CallSession = record["session"]
    svc = _service_for(record)
    payload = dict(extracted or {})
    _append(session, MessageRole.USER, text)
    _prompt_boundary(record, text)
    stage = record["stage"]

    if stage in ("new", "verification"):
        if response_extractor.is_busy(text):
            action = svc.mark_busy(session.qualification)
            record["stage"] = "done"
        elif response_extractor.is_negative(text) and not response_extractor.is_affirmative(text):
            action = svc.verify(session.qualification, False)
            record["stage"] = "done"
        else:
            action = svc.verify(session.qualification, True)
            _apply_auto_extract(session, svc, text)
            record["stage"] = "offer"
        return action

    if stage == "offer":
        if response_extractor.is_busy(text):
            action = svc.mark_busy(session.qualification)
            record["stage"] = "done"
        elif response_extractor.is_transfer_request(text):
            action = svc.handle_turn(session.qualification, dict(payload, existing_property_loan=True))
            record["stage"] = "done"
        elif response_extractor.is_negative(text) and not response_extractor.is_affirmative(text):
            action = svc.handle_offer_reply(session.qualification, interested=False)
            record["stage"] = "done"
        else:
            if payload or response_extractor.extract(text):
                # Accepted the offer and volunteered qualification data at once.
                merged = {**response_extractor.extract(text), **dict(payload)}
                if response_extractor.is_transfer_request(text):
                    merged.setdefault("existing_property_loan", True)
                action = svc.handle_turn(session.qualification, merged)
                loan = session.qualification.loan_amount
                if loan is not None and loan > MAX_LOAN_AMOUNT:
                    record["downgrade_pending"] = True
                record["stage"] = "done" if action.end_call else "qualification"
            else:
                action = svc.handle_offer_reply(session.qualification, interested=True)
                record["stage"] = "qualification"
        return action

    # qualification stage
    # The ₹75L confirmation is resolved FIRST; normal qualification logic
    # must not run while it is pending.
    if record.get("downgrade_pending"):
        answer = response_extractor.downgrade_answer(text)
        if answer is True:
            action = svc.confirm_loan_downgrade(session.qualification, True)
            record["downgrade_pending"] = False
        elif answer is False:
            action = svc.confirm_loan_downgrade(session.qualification, False)
            record["stage"] = "done"
        else:
            from app.models.conversation import (
                ConversationAction,
                ConversationActionType,
                ConversationStage,
            )

            action = ConversationAction(
                stage=ConversationStage.QUALIFICATION,
                action=ConversationActionType.ASK_QUESTION,
                message=(
                    "The maximum available under this offer is Rs. 75 lakh. "
                    "Would you like to proceed with Rs. 75 lakh?"
                ),
                next_question="loan_amount",
            )
        return action

    # Natural-language slots first; explicit harness/LLM payload wins ties.
    # The currently-asked question routes context-free amounts (loan vs market).
    pending_q = svc.qualification.get_next_question(session.qualification)
    extracted = dict(response_extractor.extract(text, prefer=pending_q))
    if (
        session.qualification.documents_available is None
        and "documents_available" not in extracted
        and not payload
        and svc.qualification.get_next_question(session.qualification) == "documents_available"
    ):
        # Bare "yes"/"no" answers the boolean question currently being asked.
        if response_extractor.is_affirmative(text) and not response_extractor.is_negative(text):
            extracted["documents_available"] = True
        elif response_extractor.is_negative(text):
            extracted["documents_available"] = False
    extracted.update(payload or {})
    if response_extractor.is_transfer_request(text):
        extracted.setdefault("existing_property_loan", True)
    action = svc.handle_turn(session.qualification, extracted)
    _loan = session.qualification.loan_amount
    if _loan is not None and _loan > MAX_LOAN_AMOUNT:
        record["downgrade_pending"] = True
    if (
        session.qualification.property_type is None
        and action.next_question == "property_type"
        and response_extractor.ambiguous_property(text)
    ):
        action.message = (
            "Just to confirm — is your property residential, commercial, "
            "industrial, or agricultural?"
        )
    if action.end_call:
        record["stage"] = "done"
    return action
