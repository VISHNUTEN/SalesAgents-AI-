"""Qualification state models (Step 2: structural only, no eligibility logic)."""

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    AGRICULTURAL = "agricultural"


class OwnershipStatus(str, Enum):
    SOLE = "sole"
    JOINT = "joint"


class OccupationType(str, Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"


class IncomeMode(str, Enum):
    BANK = "bank"
    CASH = "cash"


class QualificationState(BaseModel):
    customer_verified: Optional[bool] = None
    property_type: Optional[PropertyType] = None
    ownership_status: Optional[OwnershipStatus] = None
    documents_available: Optional[bool] = None
    loan_amount: Optional[Decimal] = Field(default=None, decimal_places=2)
    occupation: Optional[OccupationType] = None
    income_mode: Optional[IncomeMode] = None
    market_value: Optional[Decimal] = Field(default=None, decimal_places=2)
    tenure: Optional[int] = Field(default=None, strict=True)
    existing_property_loan: Optional[bool] = None
    emi_reduction_request: Optional[bool] = None

    disqualified: bool = False
    transfer_required: bool = False
