"""Conversation service: deterministic turn orchestration (Step 5).

Uses QualificationService (Step 4) + Eligibility Engine (Step 3).
No LLM, no STT/TTS, no RAG, no endpoints. Structured input only.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from app.models.conversation import (
    ConversationAction,
    ConversationActionType,
    ConversationStage,
)
from app.models.qualification import QualificationState
from app.services import eligibility_service
from app.services.eligibility_service import MAX_LOAN_AMOUNT
from app.services.qualification_service import QualificationService

QUESTION_PROMPTS = {
    "property_type": "What type of property would you like to use for this loan?",
    "ownership_status": "Is the property solely owned by you, or jointly owned?",
    "documents_available": "Do you have the original property documents available for verification?",
    "loan_amount": "What loan amount are you looking for, up to Rs. 75 lakh?",
    "occupation": "Are you salaried or self-employed?",
    "income_mode": "Does your income come into your bank account or in cash?",
    "market_value": "Approximately what is the current market value of the property?",
    "tenure": "What loan tenure would you prefer, between 3 to 15 years?",
}

DOWNGRADE_MESSAGE = (
    "The maximum available under this offer is Rs. 75 lakh. "
    "Would you like to proceed with Rs. 75 lakh?"
)


class ConversationService:
    def __init__(
        self,
        company_name: str = "Home Credit",
        agent_name: str = "Assistant",
        qualification_service: Optional[QualificationService] = None,
    ) -> None:
        self.company_name = company_name
        self.agent_name = agent_name
        self.qualification = qualification_service or QualificationService()

    # -- stages ------------------------------------------------------
    def greet(self, customer_name: str) -> ConversationAction:
        return ConversationAction(
            stage=ConversationStage.GREETING,
            action=ConversationActionType.GREETING,
            message=(
                f"Hello, this is {self.agent_name} calling from "
                f"{self.company_name}. Am I speaking with {customer_name}?"
            ),
            next_question=None,
            end_call=False,
        )

    def verify(
        self, state: QualificationState, success: bool
    ) -> ConversationAction:
        if success:
            state.customer_verified = True
            return ConversationAction(
                stage=ConversationStage.OFFER,
                action=ConversationActionType.PRESENT_OFFER,
                message=(
                    "Thanks for confirming. You may be eligible for a special "
                    "pre-approved Loan Against Property offer of up to "
                    "Rs. 75 lakh, subject to final eligibility. "
                    "Do you have 2-3 minutes to check suitability?"
                ),
            )
        return ConversationAction(
            stage=ConversationStage.COMPLETED,
            action=ConversationActionType.END_CALL,
            message="Thank you for your time. Goodbye.",
            end_call=True,
        )

    def mark_busy(self, state: QualificationState) -> ConversationAction:
        return ConversationAction(
            stage=ConversationStage.CALLBACK,
            action=ConversationActionType.REQUEST_CALLBACK,
            message=(
                "Certainly. What would be a convenient time for us to call you back?"
            ),
            end_call=True,
        )

    def handle_offer_reply(
        self, state: QualificationState, interested: bool, is_busy: bool = False
    ) -> ConversationAction:
        if is_busy:
            return self.mark_busy(state)
        if not interested:
            return ConversationAction(
                stage=ConversationStage.COMPLETED,
                action=ConversationActionType.END_CALL,
                message="Thank you for your time. Goodbye.",
                end_call=True,
            )
        return self._ask_next(state)

    # -- qualification turns -----------------------------------------
    def handle_turn(
        self, state: QualificationState, extracted: Dict[str, Any]
    ) -> ConversationAction:
        updated = self.qualification.update_state(state, extracted)
        # Sync back onto the caller's object so tests/callers see new values.
        for field in type(state).model_fields:
            setattr(state, field, getattr(updated, field))
        result = self.qualification.evaluate(state)

        if result.status.value == "transfer_required":
            return ConversationAction(
                stage=ConversationStage.TRANSFER,
                action=ConversationActionType.TRANSFER,
                message=(
                    "Thank you for clarifying. A loan-transfer specialist "
                    "will contact you shortly. Thank you for your time."
                ),
                end_call=True,
                transfer_required=True,
            )
        if result.status.value == "disqualified":
            return ConversationAction(
                stage=ConversationStage.DISQUALIFIED,
                action=ConversationActionType.DISQUALIFY,
                message=(
                    f"Thank you for sharing that. {result.reason or ''} "
                    "You don't meet the criteria for this specific offer "
                    "at this time. Thank you for your time."
                ),
                end_call=True,
            )
        if result.status.value == "qualified":
            return ConversationAction(
                stage=ConversationStage.QUALIFIED,
                action=ConversationActionType.QUALIFY,
                message=(
                    "Thank you. You meet the preliminary criteria. "
                    "A senior loan expert will call you shortly to discuss "
                    "next steps. Exact interest rates will be shared by them."
                ),
                end_call=True,
            )
        # Pending: over-limit downgrade confirm takes precedence.
        if (
            state.loan_amount is not None
            and state.loan_amount > MAX_LOAN_AMOUNT
        ):
            return ConversationAction(
                stage=ConversationStage.QUALIFICATION,
                action=ConversationActionType.ASK_QUESTION,
                message=DOWNGRADE_MESSAGE,
                next_question="loan_amount",
            )
        return self._ask_next(state)

    def confirm_loan_downgrade(
        self, state: QualificationState, accepted: bool
    ) -> ConversationAction:
        if accepted:
            state.loan_amount = Decimal(str(MAX_LOAN_AMOUNT))
            return self._ask_next(state)
        return ConversationAction(
            stage=ConversationStage.COMPLETED,
            action=ConversationActionType.END_CALL,
            message="Thank you for your time. Goodbye.",
            end_call=True,
        )

    # -- helpers ------------------------------------------------------
    def _ask_next(self, state: QualificationState) -> ConversationAction:
        next_question = self.qualification.get_next_question(state)
        if next_question is None:
            # Complete (or terminal with no disqualify/transfer info).
            result = self.qualification.evaluate(state)
            if result.status.value == "qualified":
                return ConversationAction(
                    stage=ConversationStage.QUALIFIED,
                    action=ConversationActionType.QUALIFY,
                    message=(
                        "Thank you. You meet the preliminary criteria. "
                        "A senior loan expert will call you shortly."
                    ),
                    end_call=True,
                )
            return ConversationAction(
                stage=ConversationStage.COMPLETED,
                action=ConversationActionType.END_CALL,
                message="Thank you for your time. Goodbye.",
                end_call=True,
            )
        _ = eligibility_service  # keep Step-3 linkage explicit; no direct use here.
        return ConversationAction(
            stage=ConversationStage.QUALIFICATION,
            action=ConversationActionType.ASK_QUESTION,
            message=QUESTION_PROMPTS.get(next_question, next_question),
            next_question=next_question,
        )
