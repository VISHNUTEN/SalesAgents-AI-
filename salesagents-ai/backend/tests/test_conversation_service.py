"""Step 5: conversation service tests (deterministic, structured input only)."""

from decimal import Decimal

from app.models.conversation import ConversationActionType, ConversationStage
from app.models.qualification import (
    IncomeMode,
    OccupationType,
    OwnershipStatus,
    PropertyType,
    QualificationState,
)
from app.services.conversation_service import ConversationService


def _svc() -> ConversationService:
    return ConversationService(company_name="Home Credit", agent_name="TestAgent")


def _full_valid() -> QualificationState:
    return QualificationState(
        customer_verified=True,
        property_type=PropertyType.RESIDENTIAL,
        ownership_status=OwnershipStatus.SOLE,
        documents_available=True,
        loan_amount=Decimal("5000000"),
        occupation=OccupationType.SALARIED,
        income_mode=IncomeMode.BANK,
        market_value=Decimal("10000000"),
        tenure=10,
    )


def test_initial_greeting():
    action = _svc().greet("Rahul")
    assert action.stage == ConversationStage.GREETING
    assert action.action == ConversationActionType.GREETING
    assert "Rahul" in action.message
    assert action.end_call is False


def test_successful_verification_goes_to_offer():
    svc = _svc()
    state = QualificationState()
    action = svc.verify(state, True)
    assert state.customer_verified is True
    assert action.stage == ConversationStage.OFFER
    assert action.action == ConversationActionType.PRESENT_OFFER


def test_failed_verification_ends_call():
    action = _svc().verify(QualificationState(), False)
    assert action.end_call is True
    assert action.action == ConversationActionType.END_CALL


def test_busy_customer_callback():
    action = _svc().mark_busy(QualificationState())
    assert action.stage == ConversationStage.CALLBACK
    assert action.action == ConversationActionType.REQUEST_CALLBACK
    assert action.end_call is True
    assert action.next_question is None


def test_interested_customer_starts_qualification():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_offer_reply(state, interested=True)
    assert action.stage == ConversationStage.QUALIFICATION
    assert action.action == ConversationActionType.ASK_QUESTION
    assert action.next_question == "property_type"


def test_existing_loan_transfer():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(state, {"existing_property_loan": True})
    assert action.action == ConversationActionType.TRANSFER
    assert action.transfer_required is True
    assert action.end_call is True


def test_emi_reduction_transfer():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(state, {"emi_reduction_request": True})
    assert action.action == ConversationActionType.TRANSFER
    assert action.end_call is True


def test_agricultural_disqualified():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(state, {"property_type": PropertyType.AGRICULTURAL})
    assert action.action == ConversationActionType.DISQUALIFY
    assert action.end_call is True
    assert action.next_question is None


def test_cash_income_disqualified():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(state, {"income_mode": IncomeMode.CASH})
    assert action.action == ConversationActionType.DISQUALIFY
    assert action.end_call is True


def test_incomplete_asks_earliest_missing():
    svc = _svc()
    state = QualificationState(
        customer_verified=True,
        property_type=PropertyType.RESIDENTIAL,
        ownership_status=OwnershipStatus.JOINT,
        documents_available=True,
        loan_amount=Decimal("5000000"),
        occupation=OccupationType.SALARIED,
        income_mode=IncomeMode.BANK,
        market_value=Decimal("10000000"),
        tenure=None,
    )
    action = svc.handle_turn(state, {})
    assert action.action == ConversationActionType.ASK_QUESTION
    assert action.next_question == "tenure"


def test_fully_qualified_handoff():
    svc = _svc()
    action = svc.handle_turn(_full_valid(), {})
    assert action.action == ConversationActionType.QUALIFY
    assert action.stage == ConversationStage.QUALIFIED
    assert action.end_call is True


def test_loan_above_max_accept_and_reject():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    asked = svc.handle_turn(state, {"loan_amount": Decimal("9000000")})
    assert asked.next_question == "loan_amount"
    assert "75" in asked.message
    assert asked.end_call is False

    accepted = svc.confirm_loan_downgrade(state, True)
    assert state.loan_amount == Decimal("7500000")
    assert accepted.action == ConversationActionType.ASK_QUESTION

    state2 = QualificationState(
        customer_verified=True, loan_amount=Decimal("9000000")
    )
    rejected = svc.confirm_loan_downgrade(state2, False)
    assert rejected.end_call is True
    assert rejected.action == ConversationActionType.END_CALL


def test_out_of_order_retains_values():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(
        state, {"loan_amount": Decimal("5000000"), "tenure": 10}
    )
    assert state.loan_amount == Decimal("5000000")
    assert state.tenure == 10
    assert action.next_question == "property_type"


def test_multiple_answers_one_turn():
    svc = _svc()
    state = QualificationState(customer_verified=True)
    action = svc.handle_turn(
        state,
        {
            "property_type": PropertyType.RESIDENTIAL,
            "ownership_status": OwnershipStatus.JOINT,
            "documents_available": True,
            "loan_amount": Decimal("5000000"),
        },
    )
    assert state.property_type == PropertyType.RESIDENTIAL
    assert state.ownership_status == OwnershipStatus.JOINT
    assert action.action == ConversationActionType.ASK_QUESTION
    assert action.next_question == "occupation"
