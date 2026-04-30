from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class UploadedDocument(BaseModel):
    file_id: str
    file_name: str
    file_content: str = ""        # base64-encoded image or URL
    actual_type: Optional[str] = None   # set in test cases to skip LLM classify
    quality: Optional[str] = None       # set in test cases to skip quality check
    content: Optional[Dict[str, Any]] = None  # pre-populated extraction data for test cases


class PriorClaim(BaseModel):
    claim_id: str
    date: date
    amount: float
    provider: str


class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float = Field(..., gt=0)
    hospital_name: Optional[str] = None
    diagnosis: Optional[str] = None     # direct diagnosis shortcut for test cases
    documents: List[UploadedDocument] = Field(default_factory=list)
    claims_history: Optional[List[PriorClaim]] = None
    ytd_claims_amount: Optional[float] = 0.0
    simulate_component_failure: Optional[bool] = False

    @field_validator("claimed_amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("claimed_amount must be greater than 0")
        return v


class ClaimResponse(BaseModel):
    claim_id: str
    status: str  # "completed" | "stopped_early"
    decision: Optional[str] = None
    approved_amount: Optional[float] = None
    confidence_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    trace: Any = None
    errors: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
