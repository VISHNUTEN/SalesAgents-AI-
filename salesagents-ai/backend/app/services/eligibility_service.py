"""Eligibility engine: QualificationState -> EligibilityResult (Step 3).

No I/O, no LLM, no conversation text. Pure deterministic rules.
"""

from decimal import Decimal
from typing import Optional

from app.models.eligibility import EligibilityResult, EligibilityStatus
from app.models.qualification import IncomeMode, PropertyType, QualificationState

MAX_LOAN_AMOUNT = Decimal("7500000")
MIN_TENURE = 3
MAX_TENURE = 15


def check_transfer_condition(state: QualificationState) -> Optional[str]:
    if state.existing_property_loan is True or state.emi_reduction_request is True:
        return "Customer requires the loan-transfer specialist."
    return None


def check_property_type(state: QualificationState) -> Optional[str]:
    if state.property_type == PropertyType.AGRICULTURAL:
        return "Agricultural property is not eligible."
    return None


def check_documents(state: QualificationState) -> Optional[str]:
    if state.documents_available is False:
        return "Original property documents are required."
    return None


def check_income_mode(state: QualificationState) -> Optional[str]:
    if state.income_mode == IncomeMode.CASH:
        return "Cash income is not eligible."
    return None


def check_tenure(state: QualificationState) -> Optional[str]:
    if state.tenure is None:
        return None
    if state.tenure < MIN_TENURE or state.tenure > MAX_TENURE:
        return f"Tenure must be between {MIN_TENURE} and {MAX_TENURE} years."
    return None


def check_loan_amount(state: QualificationState) -> Optional[str]:
    # > max is NOT auto-disqualification; conversation layer handles
    # the downgrade confirm. Return pending reason so we never
    # mark an over-limit request as qualified.
    if state.loan_amount is None:
        return None
    if state.loan_amount > MAX_LOAN_AMOUNT:
        return "Loan amount exceeds Rs. 75 lakh maximum; needs downgrade confirmation."
    return None


def _is_complete(state: QualificationState) -> bool:
    return all(
        [
            state.property_type is not None,
            state.ownership_status is not None,
            state.documents_available is not None,
            state.loan_amount is not None,
            state.occupation is not None,
            state.income_mode is not None,
            state.market_value is not None,
            state.tenure is not None,
        ]
    )


def evaluate(state: QualificationState) -> EligibilityResult:
    transfer_reason = check_transfer_condition(state)
    if transfer_reason:
        return EligibilityResult(
            status=EligibilityStatus.TRANSFER_REQUIRED,
            eligible=False,
            disqualified=False,
            transfer_required=True,
            reason=transfer_reason,
        )

    for check in (
        check_property_type,
        check_documents,
        check_income_mode,
        check_tenure,
    ):
        reason = check(state)
        if reason:
            return EligibilityResult(
                status=EligibilityStatus.DISQUALIFIED,
                eligible=False,
                disqualified=True,
                transfer_required=False,
                reason=reason,
            )

    loan_reason = check_loan_amount(state)
    if loan_reason:
        return EligibilityResult(
            status=EligibilityStatus.PENDING,
            eligible=False,
            disqualified=False,
            transfer_required=False,
            reason=loan_reason,
        )

    if not _is_complete(state):
        return EligibilityResult(
            status=EligibilityStatus.PENDING,
            eligible=False,
            disqualified=False,
            transfer_required=False,
            reason="Qualification information is incomplete.",
        )

    return EligibilityResult(
        status=EligibilityStatus.QUALIFIED,
        eligible=True,
        disqualified=False,
        transfer_required=False,
        reason=None,
    )
