"""Step 3: eligibility engine unit tests (no LLM, no I/O)."""

from decimal import Decimal

from app.models.eligibility import EligibilityStatus
from app.models.qualification import (
    IncomeMode,
    OccupationType,
    OwnershipStatus,
    PropertyType,
    QualificationState,
)
from app.services import eligibility_service


def _valid_state(**overrides):
    base = dict(
        customer_verified=True,
        property_type=PropertyType.RESIDENTIAL,
        ownership_status=OwnershipStatus.SOLE,
        documents_available=True,
        loan_amount=Decimal("5000000"),
        occupation=OccupationType.SALARIED,
        income_mode=IncomeMode.BANK,
        market_value=Decimal("10000000"),
        tenure=10,
        existing_property_loan=False,
        emi_reduction_request=False,
    )
    base.update(overrides)
    return QualificationState(**base)


def test_valid_residential_customer_qualified():
    result = eligibility_service.evaluate(_valid_state())
    assert result.status == EligibilityStatus.QUALIFIED
    assert result.eligible is True


def test_agricultural_disqualified():
    result = eligibility_service.evaluate(
        _valid_state(property_type=PropertyType.AGRICULTURAL)
    )
    assert result.status == EligibilityStatus.DISQUALIFIED
    assert result.disqualified is True


def test_cash_income_disqualified():
    result = eligibility_service.evaluate(_valid_state(income_mode=IncomeMode.CASH))
    assert result.status == EligibilityStatus.DISQUALIFIED
    assert result.disqualified is True


def test_missing_documents_disqualified():
    result = eligibility_service.evaluate(_valid_state(documents_available=False))
    assert result.status == EligibilityStatus.DISQUALIFIED


def test_tenure_below_minimum_disqualified():
    result = eligibility_service.evaluate(_valid_state(tenure=2))
    assert result.status == EligibilityStatus.DISQUALIFIED


def test_tenure_above_maximum_disqualified():
    result = eligibility_service.evaluate(_valid_state(tenure=16))
    assert result.status == EligibilityStatus.DISQUALIFIED


def test_boundary_tenure_accepted():
    for tenure in (3, 15):
        result = eligibility_service.evaluate(_valid_state(tenure=tenure))
        assert result.status == EligibilityStatus.QUALIFIED, tenure


def test_joint_ownership_qualified():
    result = eligibility_service.evaluate(
        _valid_state(ownership_status=OwnershipStatus.JOINT)
    )
    assert result.status == EligibilityStatus.QUALIFIED


def test_existing_loan_transfer_required():
    result = eligibility_service.evaluate(_valid_state(existing_property_loan=True))
    assert result.status == EligibilityStatus.TRANSFER_REQUIRED
    assert result.transfer_required is True
    assert result.disqualified is False


def test_emi_reduction_transfer_required():
    result = eligibility_service.evaluate(_valid_state(emi_reduction_request=True))
    assert result.status == EligibilityStatus.TRANSFER_REQUIRED
    assert result.disqualified is False


def test_missing_information_pending():
    state = QualificationState(
        property_type=PropertyType.RESIDENTIAL,
        ownership_status=OwnershipStatus.JOINT,
    )
    result = eligibility_service.evaluate(state)
    assert result.status == EligibilityStatus.PENDING
    assert result.disqualified is False


def test_market_value_no_minimum_threshold():
    low = eligibility_service.evaluate(_valid_state(market_value=Decimal("500000")))
    high = eligibility_service.evaluate(_valid_state(market_value=Decimal("50000000")))
    assert low.status == EligibilityStatus.QUALIFIED
    assert high.status == EligibilityStatus.QUALIFIED


def test_loan_above_max_not_auto_disqualified():
    result = eligibility_service.evaluate(_valid_state(loan_amount=Decimal("9000000")))
    assert result.status == EligibilityStatus.PENDING
    assert result.disqualified is False
