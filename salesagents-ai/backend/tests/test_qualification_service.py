"""Step 4: qualification service tests (structured input only, no NLP)."""

from decimal import Decimal

from app.models.eligibility import EligibilityStatus
from app.models.qualification import (
    IncomeMode,
    OccupationType,
    OwnershipStatus,
    PropertyType,
    QualificationState,
)
from app.services.qualification_service import QualificationService


def _service() -> QualificationService:
    return QualificationService()


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


def test_empty_state_next_is_property_type():
    svc = _service()
    assert svc.get_next_question(QualificationState()) == "property_type"


def test_property_provided_next_is_ownership():
    svc = _service()
    state = svc.update_state(
        QualificationState(), {"property_type": PropertyType.RESIDENTIAL}
    )
    assert state.property_type == PropertyType.RESIDENTIAL
    assert svc.get_next_question(state) == "ownership_status"


def test_multi_field_out_of_order():
    svc = _service()
    state = svc.update_state(
        QualificationState(),
        {
            "loan_amount": Decimal("5000000"),
            "tenure": 10,
            "property_type": PropertyType.RESIDENTIAL,
        },
    )
    assert state.loan_amount == Decimal("5000000")
    assert state.tenure == 10
    assert svc.get_next_question(state) == "ownership_status"


def test_multiple_fields_in_one_update():
    svc = _service()
    state = svc.update_state(
        QualificationState(),
        {
            "property_type": PropertyType.COMMERCIAL,
            "ownership_status": OwnershipStatus.JOINT,
            "documents_available": True,
            "loan_amount": Decimal("4000000"),
        },
    )
    assert state.property_type == PropertyType.COMMERCIAL
    assert state.ownership_status == OwnershipStatus.JOINT
    assert state.documents_available is True
    assert state.loan_amount == Decimal("4000000")
    assert svc.get_next_question(state) == "occupation"


def test_occupation_without_income_mode():
    svc = _service()
    state = svc.update_state(
        _full_valid(),
        {"occupation": OccupationType.SALARIED, "income_mode": None},
    )
    # reset income to unknown
    state.income_mode = None
    assert svc.get_next_question(state) == "income_mode"


def test_income_mode_without_occupation():
    svc = _service()
    state = _full_valid()
    state.occupation = None
    assert state.income_mode == IncomeMode.BANK
    assert svc.get_next_question(state) == "occupation"


def test_contradiction_latest_wins():
    svc = _service()
    state = svc.update_state(
        QualificationState(), {"property_type": PropertyType.RESIDENTIAL}
    )
    state = svc.update_state(state, {"property_type": PropertyType.COMMERCIAL})
    assert state.property_type == PropertyType.COMMERCIAL
    assert any(c.field == "property_type" for c in svc.changes)


def test_missing_fields_remain_none():
    svc = _service()
    state = svc.update_state(QualificationState(), {"property_type": PropertyType.RESIDENTIAL})
    assert state.documents_available is None
    assert state.documents_available is not False
    assert state.loan_amount is None


def test_disqualification_stops_flow():
    svc = _service()
    state = svc.update_state(
        QualificationState(), {"property_type": PropertyType.AGRICULTURAL}
    )
    result = svc.evaluate(state)
    assert result.status == EligibilityStatus.DISQUALIFIED
    assert svc.get_next_question(state) is None


def test_transfer_stops_flow():
    svc = _service()
    state = svc.update_state(
        QualificationState(), {"existing_property_loan": True}
    )
    result = svc.evaluate(state)
    assert result.status == EligibilityStatus.TRANSFER_REQUIRED
    assert svc.get_next_question(state) is None


def test_complete_qualification():
    svc = _service()
    state = _full_valid()
    result = svc.evaluate(state)
    assert result.status == EligibilityStatus.QUALIFIED
    assert svc.get_next_question(state) is None
