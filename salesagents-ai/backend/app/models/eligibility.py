"""Eligibility result models (Step 3: structural only, no rule logic here)."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EligibilityStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    TRANSFER_REQUIRED = "transfer_required"


class EligibilityResult(BaseModel):
    status: EligibilityStatus
    eligible: bool = False
    disqualified: bool = False
    transfer_required: bool = False
    reason: Optional[str] = None
