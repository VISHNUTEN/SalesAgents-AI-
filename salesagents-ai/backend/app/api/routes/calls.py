"""Call session routes (Step 7: thin orchestration, no business rules)."""

from datetime import datetime

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
from app.services import prompt_service
from app.services.eligibility_service import MAX_LOAN_AMOUNT

router = APIRouter(prefix="/api/calls", tags=["calls"])

AFFIRMATIVE = ("yes", "yeah", "yep", "sure", "okay", "this is", "speaking", "i am")
NEGATIVE = ("no,", "no.", " not ", "wrong", "not me", "not interested")
BUSY_WORDS = ("busy", "meeting", "later", "call back", "callback", "not now")
TRANSFER_WORDS = ("existing loan", "already have", "balance transfer", "transfer", "reduce", "lower my")


def _contains(text: str, words) -> bool:
    text = f" {text.lower()} "
    return any(w in text for w in words)


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
    svc = _service_for(record)
    text = request.message
    _append(session, MessageRole.USER, text)
    _prompt_boundary(record, text)
    stage = record["stage"]

    if stage in ("new", "verification"):
        if _contains(text, BUSY_WORDS):
            action = svc.mark_busy(session.qualification)
            record["stage"] = "done"
        elif _contains(text, NEGATIVE) and not _contains(text, AFFIRMATIVE):
            action = svc.verify(session.qualification, False)
            record["stage"] = "done"
        else:
            action = svc.verify(session.qualification, True)
            record["stage"] = "offer"
        _apply_action(session, record, action)
        if session.status == CallStatus.IN_PROGRESS:
            session.status = CallStatus.IN_PROGRESS
        return _to_response(session, action, CustomerMessageResponse)

    if stage == "offer":
        if _contains(text, BUSY_WORDS):
            action = svc.mark_busy(session.qualification)
            record["stage"] = "done"
        elif _contains(text, TRANSFER_WORDS):
            action = svc.handle_turn(session.qualification, dict(request.extracted, existing_property_loan=True))
            record["stage"] = "done"
        elif _contains(text, NEGATIVE) and not _contains(text, AFFIRMATIVE):
            action = svc.handle_offer_reply(session.qualification, interested=False)
            record["stage"] = "done"
        else:
            if request.extracted:
                # Accepted the offer and volunteered qualification data at once.
                extracted = dict(request.extracted)
                if _contains(text, TRANSFER_WORDS):
                    extracted.setdefault("existing_property_loan", True)
                action = svc.handle_turn(session.qualification, extracted)
                loan = session.qualification.loan_amount
                if loan is not None and loan > MAX_LOAN_AMOUNT:
                    record["downgrade_pending"] = True
                record["stage"] = "done" if action.end_call else "qualification"
            else:
                action = svc.handle_offer_reply(session.qualification, interested=True)
                record["stage"] = "qualification"
        _apply_action(session, record, action)
        return _to_response(session, action, CustomerMessageResponse)

    # qualification stage
    if record.get("downgrade_pending"):
        if _contains(text, AFFIRMATIVE):
            action = svc.confirm_loan_downgrade(session.qualification, True)
            record["downgrade_pending"] = False
        elif _contains(text, NEGATIVE):
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
        _apply_action(session, record, action)
        return _to_response(session, action, CustomerMessageResponse)

    extracted = dict(request.extracted or {})
    if _contains(text, TRANSFER_WORDS):
        extracted.setdefault("existing_property_loan", True)
    action = svc.handle_turn(session.qualification, extracted)
    _loan = session.qualification.loan_amount
    if _loan is not None and _loan > MAX_LOAN_AMOUNT:
        record["downgrade_pending"] = True
    if action.end_call:
        record["stage"] = "done"
    _apply_action(session, record, action)
    return _to_response(session, action, CustomerMessageResponse)
