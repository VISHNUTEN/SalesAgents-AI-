"""Qualification / conversation state engine (Step 4).

Manages QualificationState progress: multi-field out-of-order updates,
latest-wins contradictions, earliest-missing next question, and
Eligibility Engine integration. No LLM, no I/O, no customer-facing text.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.eligibility import EligibilityResult, EligibilityStatus
from app.models.qualification import QualificationState
from app.services import eligibility_service

# Earliest-first qualification order. Occupation + income mode share
# one stage but are tracked as two fields (occupation first).
QUESTION_ORDER: List[str] = [
    "property_type",
    "ownership_status",
    "documents_available",
    "loan_amount",
    "occupation",
    "income_mode",
    "market_value",
    "tenure",
]

ALLOWED_FIELDS = set(QUESTION_ORDER) | {
    "customer_verified",
    "existing_property_loan",
    "emi_reduction_request",
}


class StateChange(BaseModel):
    field: str
    old_value: Any = None
    new_value: Any = None

    model_config = {"arbitrary_types_allowed": True}


class QualificationService:
    def __init__(self) -> None:
        self.changes: List[StateChange] = []

    def update_state(
        self, state: QualificationState, extracted: Dict[str, Any]
    ) -> QualificationState:
        """Apply structured extraction to state.

        Only non-None values overwrite (None = not provided, not False).
        Latest explicit answer wins; every overwrite is recorded.
        Unknown keys are ignored. Revalidates via QualificationState.
        """
        updates: Dict[str, Any] = {}
        for field, value in extracted.items():
            if field not in ALLOWED_FIELDS:
                continue
            if value is None:
                continue
            old = getattr(state, field)
            if old != value:
                self.changes.append(
                    StateChange(field=field, old_value=old, new_value=value)
                )
            updates[field] = value
        if updates:
            # Revalidate through the Pydantic model (type/enum checks).
            merged = {**state.model_dump(), **updates}
            state = QualificationState(**merged)
        return state

    def get_next_question(self, state: QualificationState) -> Optional[str]:
        """Earliest unanswered item, or None if terminal/complete."""
        result = eligibility_service.evaluate(state)
        if result.status in (
            EligibilityStatus.DISQUALIFIED,
            EligibilityStatus.TRANSFER_REQUIRED,
        ):
            return None
        for field in QUESTION_ORDER:
            if getattr(state, field) is None:
                return field
        return None

    def evaluate(self, state: QualificationState) -> EligibilityResult:
        return eligibility_service.evaluate(state)

    def is_complete(self, state: QualificationState) -> bool:
        return self.get_next_question(state) is None and self.evaluate(
            state
        ).status == EligibilityStatus.QUALIFIED

    def is_terminal(self, state: QualificationState) -> bool:
        return self.evaluate(state).status in (
            EligibilityStatus.DISQUALIFIED,
            EligibilityStatus.TRANSFER_REQUIRED,
        )
