from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Decision(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class LineItemResult(BaseModel):
    description: str
    amount: float
    status: str  # "approved" | "rejected"
    reason: Optional[str] = None


class MemberEligibilityResult(BaseModel):
    passed: bool
    details: str = ""


class SubmissionDeadlineResult(BaseModel):
    passed: bool
    details: str = ""


class WaitingPeriodResult(BaseModel):
    passed: bool
    condition: Optional[str] = None
    required_days: int = 0
    actual_days: int = 0
    eligible_date: Optional[str] = None


class ExclusionCheckResult(BaseModel):
    passed: bool
    excluded_items: List[Dict[str, str]] = Field(default_factory=list)


class PreAuthCheckResult(BaseModel):
    passed: bool
    details: str = ""


class PerClaimLimitResult(BaseModel):
    passed: bool
    limit: float = 0.0
    claimed: float = 0.0


class SubLimitResult(BaseModel):
    passed: bool
    limit: float = 0.0
    amount: float = 0.0


class AnnualLimitResult(BaseModel):
    passed: bool
    limit: float = 0.0
    ytd: float = 0.0


class LimitChecks(BaseModel):
    per_claim: PerClaimLimitResult = Field(default_factory=lambda: PerClaimLimitResult(passed=True))
    sub_limit: SubLimitResult = Field(default_factory=lambda: SubLimitResult(passed=True))
    annual: AnnualLimitResult = Field(default_factory=lambda: AnnualLimitResult(passed=True))


class FinancialBreakdownItem(BaseModel):
    label: str
    amount: float


class FinancialCalculation(BaseModel):
    claimed_amount: float = 0.0
    network_discount: float = 0.0
    after_discount: float = 0.0
    copay_amount: float = 0.0
    after_copay: float = 0.0
    sub_limit_cap: float = 0.0
    approved_amount: float = 0.0
    breakdown: List[FinancialBreakdownItem] = Field(default_factory=list)


class PolicyEvalResult(BaseModel):
    member_eligible: MemberEligibilityResult = Field(
        default_factory=lambda: MemberEligibilityResult(passed=False, details="Not evaluated")
    )
    within_submission_deadline: SubmissionDeadlineResult = Field(
        default_factory=lambda: SubmissionDeadlineResult(passed=True, details="")
    )
    minimum_amount_met: bool = True
    waiting_period_check: WaitingPeriodResult = Field(
        default_factory=lambda: WaitingPeriodResult(passed=True)
    )
    exclusion_check: ExclusionCheckResult = Field(
        default_factory=lambda: ExclusionCheckResult(passed=True)
    )
    pre_auth_check: PreAuthCheckResult = Field(
        default_factory=lambda: PreAuthCheckResult(passed=True, details="")
    )
    limit_checks: LimitChecks = Field(default_factory=LimitChecks)
    financial_calculation: FinancialCalculation = Field(default_factory=FinancialCalculation)
    line_item_results: List[LineItemResult] = Field(default_factory=list)
    overall_decision: Decision = Decision.MANUAL_REVIEW
    rejection_reasons: List[str] = Field(default_factory=list)


class FraudFlag(BaseModel):
    flag_type: str
    details: str
    severity: str = "low"  # "low" | "medium" | "high"


class FraudResult(BaseModel):
    fraud_score: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: List[FraudFlag] = Field(default_factory=list)
    same_day_count: int = 0
    monthly_count: int = 0
    is_high_value: bool = False
    recommendation: str = "proceed"  # "proceed" | "flag" | "reject"


class CrossValidationResult(BaseModel):
    status: str  # "passed" | "failed"
    patient_name_match: bool = True
    date_match: bool = True
    amount_match: bool = True
    member_name_match: bool = True
    mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


class ClaimDecision(BaseModel):
    decision: Decision
    approved_amount: float = 0.0
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
