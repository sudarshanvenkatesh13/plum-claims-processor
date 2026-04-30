"""Agent 4: Pure-logic policy evaluation — zero LLM calls."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.decision import (
    AnnualLimitResult,
    Decision,
    ExclusionCheckResult,
    FinancialBreakdownItem,
    FinancialCalculation,
    LimitChecks,
    LineItemResult,
    MemberEligibilityResult,
    PerClaimLimitResult,
    PolicyEvalResult,
    PreAuthCheckResult,
    SubLimitResult,
    SubmissionDeadlineResult,
    WaitingPeriodResult,
)
from models.document import (
    BillExtraction,
    DentalReportExtraction,
    DocumentExtractionResult,
    DocumentType,
    PrescriptionExtraction,
)

logger = logging.getLogger(__name__)

# Procedure keywords that require pre-authorisation in the DIAGNOSTIC category
_PRE_AUTH_KEYWORDS = ["mri", "ct scan", "ct-scan", "pet scan", "pet-scan", "mri scan"]


def _diagnosis_from_state(state: Dict[str, Any]) -> Optional[str]:
    """Pull diagnosis from direct state key or from prescription extraction."""
    if state.get("diagnosis"):
        return state["diagnosis"]
    for er in state.get("extraction_results", []):
        if er.document_type == DocumentType.PRESCRIPTION and er.extraction:
            return getattr(er.extraction, "diagnosis", None)
    return None


def _bill_line_items(extraction_results: List[DocumentExtractionResult]) -> List[Tuple[str, float]]:
    """Return (description, amount) pairs from all HOSPITAL_BILL line items."""
    items: List[Tuple[str, float]] = []
    for er in extraction_results:
        if er.document_type == DocumentType.HOSPITAL_BILL and isinstance(er.extraction, BillExtraction):
            for li in er.extraction.line_items:
                items.append((li.description, li.amount))
    return items


def _dental_procedures(extraction_results: List[DocumentExtractionResult]) -> List[Tuple[str, float]]:
    """Return (procedure_name, amount) from dental report OR hospital bill line items."""
    # Try dental report first
    for er in extraction_results:
        if er.document_type == DocumentType.DENTAL_REPORT and isinstance(er.extraction, DentalReportExtraction):
            proc = er.extraction.procedure or ""
            total = er.extraction.total or 0.0
            if proc:
                return [(proc, total)]
    # Fall back to hospital bill line items
    return _bill_line_items(extraction_results)


def _today() -> date:
    return date.today()


async def run_policy_evaluation(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 4 (PolicyEvaluation): starting")

    policy_loader = state.get("policy_loader")
    member_id: str = state.get("member_id", "")
    category: str = state.get("claim_category", "")  # uppercase e.g. "CONSULTATION"
    treatment_date: date = state.get("treatment_date", _today())
    # submission_date defaults to treatment_date so test cases (old dates) always pass deadline
    submission_date: date = state.get("submission_date") or treatment_date
    claimed_amount: float = float(state.get("claimed_amount", 0))
    hospital_name: str = state.get("hospital_name") or ""
    ytd_claims_amount: float = float(state.get("ytd_claims_amount") or 0)
    extraction_results: List[DocumentExtractionResult] = state.get("extraction_results", [])

    rejection_reasons: List[str] = []
    cat_config = policy_loader.get_category_config(category) if policy_loader else {}

    # ══════════════════════════════════════════════════════════════════
    # CHECK 1 — Member Eligibility
    # ══════════════════════════════════════════════════════════════════
    member = policy_loader.get_member(member_id) if policy_loader else None
    if not member:
        # Try raw fallback (handles parse failures)
        raw = policy_loader.get_member_raw(member_id) if policy_loader else None
        if raw:
            member_eligible = MemberEligibilityResult(
                passed=True,
                details=f"Member {member_id} ({raw.get('name', 'Unknown')}) found via raw lookup, policy active",
            )
        else:
            member_eligible = MemberEligibilityResult(
                passed=False,
                details=f"Member {member_id} not found in policy. Please verify your member ID.",
            )
    else:
        member_eligible = MemberEligibilityResult(
            passed=True,
            details=f"Member {member.name} ({member_id}) found, policy active",
        )

    if not member_eligible.passed:
        rejection_reasons.append(member_eligible.details)
        return _build_result(
            state, rejection_reasons,
            member_eligible=member_eligible,
            overall_decision=Decision.REJECTED,
        )

    member_name = member.name if member else (policy_loader.get_member_raw(member_id) or {}).get("name", member_id)

    # ══════════════════════════════════════════════════════════════════
    # CHECK 2 — Submission Deadline
    # ══════════════════════════════════════════════════════════════════
    deadline_days = policy_loader.get_submission_deadline_days() if policy_loader else 30
    days_since = (submission_date - treatment_date).days
    if days_since > deadline_days:
        within_deadline = SubmissionDeadlineResult(
            passed=False,
            details=(
                f"Claim submitted {days_since} days after treatment date. "
                f"Deadline is {deadline_days} days from treatment date."
            ),
        )
        rejection_reasons.append(within_deadline.details)
    else:
        within_deadline = SubmissionDeadlineResult(
            passed=True,
            details=f"Submitted within {deadline_days}-day window ({days_since} days after treatment).",
        )

    # ══════════════════════════════════════════════════════════════════
    # CHECK 3 — Minimum Claim Amount
    # ══════════════════════════════════════════════════════════════════
    min_amount = policy_loader.get_minimum_claim_amount() if policy_loader else 500
    minimum_amount_met = claimed_amount >= min_amount
    if not minimum_amount_met:
        rejection_reasons.append(
            f"Claimed amount ₹{claimed_amount:,.0f} is below the minimum claim amount of ₹{min_amount:,.0f}."
        )

    # ══════════════════════════════════════════════════════════════════
    # CHECK 4 — Waiting Period
    # ══════════════════════════════════════════════════════════════════
    diagnosis = _diagnosis_from_state(state)
    waiting_period_check = _check_waiting_period(
        policy_loader, member_id, treatment_date, diagnosis, rejection_reasons
    )

    # ══════════════════════════════════════════════════════════════════
    # CHECK 5 — Exclusion Check
    # ══════════════════════════════════════════════════════════════════
    exclusion_check, line_item_results, eligible_amount = _check_exclusions(
        policy_loader, category, diagnosis, claimed_amount, extraction_results, rejection_reasons
    )

    # ══════════════════════════════════════════════════════════════════
    # CHECK 6 — Pre-Authorization
    # ══════════════════════════════════════════════════════════════════
    pre_auth_check = _check_pre_auth(
        policy_loader, category, claimed_amount, extraction_results, diagnosis, rejection_reasons
    )

    # ══════════════════════════════════════════════════════════════════
    # Early-exit for hard REJECTED conditions
    # ══════════════════════════════════════════════════════════════════
    if (
        not within_deadline.passed
        or not minimum_amount_met
        or not waiting_period_check.passed
        or not exclusion_check.passed and eligible_amount == 0  # ALL items excluded
        or not pre_auth_check.passed
    ):
        # Determine overall: if some items eligible → PARTIAL, else REJECTED
        overall = Decision.PARTIAL if (eligible_amount > 0 and not exclusion_check.passed) else Decision.REJECTED
        if overall == Decision.REJECTED:
            fin = FinancialCalculation(claimed_amount=claimed_amount, approved_amount=0)
            return _build_result(
                state, rejection_reasons,
                member_eligible=member_eligible,
                within_deadline=within_deadline,
                minimum_amount_met=minimum_amount_met,
                waiting_period_check=waiting_period_check,
                exclusion_check=exclusion_check,
                pre_auth_check=pre_auth_check,
                line_item_results=line_item_results,
                financial_calculation=fin,
                overall_decision=Decision.REJECTED,
            )

    # ══════════════════════════════════════════════════════════════════
    # CHECK 7 — Per-Claim Limit
    # (uses eligible_amount — after exclusions — vs effective cap)
    # ══════════════════════════════════════════════════════════════════
    per_claim_limit = policy_loader.get_per_claim_limit() if policy_loader else 5000
    cat_sub_limit = float(cat_config.get("sub_limit", 0))
    # Effective per-claim cap: use category sub_limit if it's higher than the baseline
    effective_per_claim_cap = max(per_claim_limit, cat_sub_limit) if cat_sub_limit > 0 else per_claim_limit

    if eligible_amount > effective_per_claim_cap:
        per_claim = PerClaimLimitResult(passed=False, limit=effective_per_claim_cap, claimed=eligible_amount)
        msg = (
            f"Claimed amount of ₹{eligible_amount:,.0f} exceeds the per-claim limit "
            f"of ₹{effective_per_claim_cap:,.0f} for {category.title()} claims."
        )
        rejection_reasons.append(msg)
        fin = FinancialCalculation(claimed_amount=claimed_amount, approved_amount=0)
        return _build_result(
            state, rejection_reasons,
            member_eligible=member_eligible,
            within_deadline=within_deadline,
            minimum_amount_met=minimum_amount_met,
            waiting_period_check=waiting_period_check,
            exclusion_check=exclusion_check,
            pre_auth_check=pre_auth_check,
            limit_checks=LimitChecks(
                per_claim=per_claim,
                sub_limit=SubLimitResult(passed=True, limit=cat_sub_limit, amount=eligible_amount),
                annual=AnnualLimitResult(passed=True),
            ),
            line_item_results=line_item_results,
            financial_calculation=fin,
            overall_decision=Decision.REJECTED,
        )
    else:
        per_claim = PerClaimLimitResult(passed=True, limit=effective_per_claim_cap, claimed=eligible_amount)

    # ══════════════════════════════════════════════════════════════════
    # CHECK 8 — Sub-Limit Cap (soft — caps approved amount)
    # ══════════════════════════════════════════════════════════════════
    if cat_sub_limit > 0 and eligible_amount > cat_sub_limit:
        sub_limit_check = SubLimitResult(passed=False, limit=cat_sub_limit, amount=eligible_amount)
        capped_amount = cat_sub_limit
        rejection_reasons.append(
            f"Approved amount capped at category sub-limit of ₹{cat_sub_limit:,.0f}."
        )
    else:
        sub_limit_check = SubLimitResult(passed=True, limit=cat_sub_limit, amount=eligible_amount)
        capped_amount = eligible_amount

    # ══════════════════════════════════════════════════════════════════
    # CHECK 9 — Annual Limit
    # ══════════════════════════════════════════════════════════════════
    annual_limit = policy_loader.get_annual_limit() if policy_loader else 50000
    annual_remaining = annual_limit - ytd_claims_amount
    if capped_amount > annual_remaining:
        annual_check = AnnualLimitResult(passed=False, limit=annual_limit, ytd=ytd_claims_amount)
        capped_amount = max(annual_remaining, 0)
        rejection_reasons.append(
            f"Annual OPD limit reached. Remaining balance: ₹{annual_remaining:,.0f}."
        )
    else:
        annual_check = AnnualLimitResult(passed=True, limit=annual_limit, ytd=ytd_claims_amount)

    # ══════════════════════════════════════════════════════════════════
    # CHECK 10 — Financial Calculation
    # Network discount FIRST, then copay on the discounted amount
    # ══════════════════════════════════════════════════════════════════
    is_network = policy_loader.is_network_hospital(hospital_name) if policy_loader else False
    network_discount_pct = float(cat_config.get("network_discount_percent", 0)) / 100 if is_network else 0.0
    copay_pct = float(cat_config.get("copay_percent", 0)) / 100

    breakdown: List[FinancialBreakdownItem] = []
    breakdown.append(FinancialBreakdownItem(label=f"Eligible amount (after exclusions)", amount=capped_amount))

    network_discount_amount = round(capped_amount * network_discount_pct, 2)
    after_discount = round(capped_amount - network_discount_amount, 2)
    if network_discount_amount > 0:
        breakdown.append(
            FinancialBreakdownItem(
                label=f"Network hospital discount ({int(network_discount_pct*100)}%)",
                amount=-network_discount_amount,
            )
        )
        breakdown.append(FinancialBreakdownItem(label="After network discount", amount=after_discount))

    copay_amount = round(after_discount * copay_pct, 2)
    after_copay = round(after_discount - copay_amount, 2)
    if copay_amount > 0:
        breakdown.append(
            FinancialBreakdownItem(label=f"Co-pay ({int(copay_pct*100)}%)", amount=-copay_amount)
        )

    # Final cap at sub-limit (in case after-discount amount is > sub_limit — shouldn't happen but be safe)
    approved_amount = min(after_copay, cat_sub_limit) if cat_sub_limit > 0 else after_copay
    breakdown.append(FinancialBreakdownItem(label="Approved amount", amount=approved_amount))

    fin = FinancialCalculation(
        claimed_amount=claimed_amount,
        network_discount=network_discount_amount,
        after_discount=after_discount,
        copay_amount=copay_amount,
        after_copay=after_copay,
        sub_limit_cap=cat_sub_limit,
        approved_amount=approved_amount,
        breakdown=breakdown,
    )

    # Determine decision
    has_partial = not exclusion_check.passed and eligible_amount > 0
    has_capped = not sub_limit_check.passed
    if rejection_reasons and approved_amount <= 0:
        overall = Decision.REJECTED
    elif has_partial or has_capped:
        overall = Decision.PARTIAL
    else:
        overall = Decision.APPROVED

    limit_checks = LimitChecks(
        per_claim=per_claim,
        sub_limit=sub_limit_check,
        annual=annual_check,
    )

    logger.info(
        "Agent 4: decision=%s, approved=%.2f, eligible=%.2f",
        overall.value, approved_amount, eligible_amount,
    )

    return _build_result(
        state, rejection_reasons,
        member_eligible=member_eligible,
        within_deadline=within_deadline,
        minimum_amount_met=minimum_amount_met,
        waiting_period_check=waiting_period_check,
        exclusion_check=exclusion_check,
        pre_auth_check=pre_auth_check,
        limit_checks=limit_checks,
        line_item_results=line_item_results,
        financial_calculation=fin,
        overall_decision=overall,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helper sub-check functions
# ──────────────────────────────────────────────────────────────────────────────

def _check_waiting_period(
    policy_loader,
    member_id: str,
    treatment_date: date,
    diagnosis: Optional[str],
    rejection_reasons: List[str],
) -> WaitingPeriodResult:
    join_date_str = policy_loader.get_member_join_date(member_id)
    if not join_date_str:
        return WaitingPeriodResult(passed=True)

    try:
        join_date = date.fromisoformat(join_date_str)
    except ValueError:
        return WaitingPeriodResult(passed=True)

    actual_days = (treatment_date - join_date).days

    # Get condition-specific waiting period (longest applicable)
    condition_key, condition_days = policy_loader.get_waiting_period_for_diagnosis(diagnosis or "")
    initial_days = policy_loader.get_initial_waiting_period()
    required_days = max(initial_days, condition_days)

    eligible_date_obj = join_date + timedelta(days=required_days)
    eligible_date_str = eligible_date_obj.isoformat()

    passed = actual_days >= required_days

    if not passed:
        cond_label = condition_key.replace("_", " ").title() if condition_key else "policy"
        rejection_reasons.append(
            f"Waiting period not completed for {cond_label}. "
            f"Policy requires {required_days} days; only {actual_days} days have elapsed since join date "
            f"({join_date_str}). Eligible from {eligible_date_str}."
        )

    return WaitingPeriodResult(
        passed=passed,
        condition=condition_key,
        required_days=required_days,
        actual_days=actual_days,
        eligible_date=eligible_date_str if not passed else None,
    )


def _check_exclusions(
    policy_loader,
    category: str,
    diagnosis: Optional[str],
    claimed_amount: float,
    extraction_results: List[DocumentExtractionResult],
    rejection_reasons: List[str],
) -> Tuple[ExclusionCheckResult, List[LineItemResult], float]:
    """
    Returns (ExclusionCheckResult, line_item_results, eligible_amount).
    eligible_amount = sum of approved line items (or claimed_amount if no line items).
    """
    excluded_items = []

    # Check diagnosis against general exclusions (TC012 obesity/bariatric)
    if diagnosis and policy_loader:
        matched_excl = policy_loader.get_matching_exclusion(diagnosis)
        if matched_excl:
            excluded_items.append({"item": diagnosis, "reason": f"Excluded condition: {matched_excl}"})
            rejection_reasons.append(
                f"Diagnosis '{diagnosis}' falls under policy exclusion: '{matched_excl}'. "
                f"This condition/procedure is not covered under this policy."
            )
            # Whole claim excluded
            return (
                ExclusionCheckResult(passed=False, excluded_items=excluded_items),
                [],
                0.0,
            )

    # Category-specific line-item exclusion check (TC006 dental)
    line_item_results: List[LineItemResult] = []
    cat_excl_list = policy_loader.get_category_exclusions(category) if policy_loader else []

    # Get line items for this category
    if category.upper() == "DENTAL":
        procedures = _dental_procedures(extraction_results)
    else:
        procedures = _bill_line_items(extraction_results)

    if procedures:
        approved_total = 0.0
        for desc, amount in procedures:
            is_excluded = _procedure_matches_exclusions(desc, cat_excl_list)
            if is_excluded:
                excl_reason = next(
                    (e for e in cat_excl_list if e.lower() in desc.lower() or desc.lower() in e.lower()),
                    "Excluded procedure",
                )
                line_item_results.append(
                    LineItemResult(
                        description=desc,
                        amount=amount,
                        status="rejected",
                        reason=f"Excluded: {excl_reason}",
                    )
                )
                excluded_items.append({"item": desc, "reason": excl_reason})
            else:
                line_item_results.append(
                    LineItemResult(description=desc, amount=amount, status="approved")
                )
                approved_total += amount

        if not excluded_items:
            return ExclusionCheckResult(passed=True), line_item_results, claimed_amount

        if approved_total == 0:
            rejection_reasons.append(
                f"All line items excluded for {category.title()} claim. No payable amount."
            )
            return (
                ExclusionCheckResult(passed=False, excluded_items=excluded_items),
                line_item_results,
                0.0,
            )

        # Partial — some items excluded
        for item in excluded_items:
            rejection_reasons.append(
                f"Line item '{item['item']}' excluded: {item['reason']}."
            )
        return (
            ExclusionCheckResult(passed=False, excluded_items=excluded_items),
            line_item_results,
            approved_total,
        )

    # No line items — check whole claim amount (no partial possible)
    return ExclusionCheckResult(passed=True), [], claimed_amount


def _procedure_matches_exclusions(procedure: str, exclusion_list: List[str]) -> bool:
    proc_lower = procedure.lower()
    for excl in exclusion_list:
        if excl.lower() in proc_lower or proc_lower in excl.lower():
            return True
    return False


def _dental_procedures(extraction_results: List[DocumentExtractionResult]) -> List[Tuple[str, float]]:
    for er in extraction_results:
        if er.document_type == DocumentType.DENTAL_REPORT and isinstance(er.extraction, DentalReportExtraction):
            proc = er.extraction.procedure or ""
            total = er.extraction.total or 0.0
            if proc:
                return [(proc, total)]
    return _bill_line_items(extraction_results)


def _bill_line_items(extraction_results: List[DocumentExtractionResult]) -> List[Tuple[str, float]]:
    items = []
    for er in extraction_results:
        if er.document_type == DocumentType.HOSPITAL_BILL and isinstance(er.extraction, BillExtraction):
            for li in er.extraction.line_items:
                items.append((li.description, li.amount))
    return items


def _check_pre_auth(
    policy_loader,
    category: str,
    claimed_amount: float,
    extraction_results: List[DocumentExtractionResult],
    diagnosis: Optional[str],
    rejection_reasons: List[str],
) -> PreAuthCheckResult:
    if category.upper() != "DIAGNOSTIC":
        return PreAuthCheckResult(passed=True, details="Pre-auth not required for this category")

    cat_config = policy_loader.get_category_config(category) if policy_loader else {}
    pre_auth_threshold = float(cat_config.get("pre_auth_threshold", 10000))
    high_value_tests = [t.lower() for t in cat_config.get("high_value_tests_requiring_pre_auth", [])]

    # Gather all test/procedure descriptions from extractions
    descriptions: List[str] = []
    if diagnosis:
        descriptions.append(diagnosis)
    for er in extraction_results:
        ext = er.extraction
        if ext is None:
            continue
        # DiagnosticReport: modality field (e.g. "MRI", "CT Scan")
        if hasattr(ext, "modality") and ext.modality:
            descriptions.append(ext.modality)
        # LabReport: test names
        if hasattr(ext, "tests"):
            descriptions.extend(t.name for t in getattr(ext, "tests", []))
        # Prescription: tests_ordered list (e.g. ["MRI Lumbar Spine"])
        if hasattr(ext, "tests_ordered"):
            descriptions.extend(getattr(ext, "tests_ordered", []))
        # Hospital bill: line item descriptions
        if hasattr(ext, "line_items"):
            descriptions.extend(li.description for li in getattr(ext, "line_items", []))

    # Check if any high-value test is present and amount > threshold (TC007)
    for desc in descriptions:
        desc_lower = desc.lower()
        for test_kw in high_value_tests:
            if test_kw in desc_lower:
                if claimed_amount > pre_auth_threshold:
                    msg = (
                        f"Pre-authorization required: '{desc}' above ₹{pre_auth_threshold:,.0f} "
                        f"requires pre-authorization before reimbursement. "
                        f"Please obtain pre-auth from your insurer and resubmit the claim "
                        f"with the pre-authorization reference number."
                    )
                    rejection_reasons.append(msg)
                    return PreAuthCheckResult(passed=False, details=msg)
                break

    # Also check if the description directly mentions MRI/CT/PET (TC007)
    for kw in _PRE_AUTH_KEYWORDS:
        for desc in descriptions:
            if kw in desc.lower() and claimed_amount > pre_auth_threshold:
                msg = (
                    f"Pre-authorization required: '{desc.upper()}' above ₹{pre_auth_threshold:,.0f} "
                    f"requires pre-authorization. Please obtain pre-auth and resubmit."
                )
                rejection_reasons.append(msg)
                return PreAuthCheckResult(passed=False, details=msg)

    return PreAuthCheckResult(passed=True, details="Pre-auth not required for this test/amount")


# ──────────────────────────────────────────────────────────────────────────────
# State builder
# ──────────────────────────────────────────────────────────────────────────────

def _build_result(
    state: Dict[str, Any],
    rejection_reasons: List[str],
    member_eligible: MemberEligibilityResult = None,
    within_deadline: SubmissionDeadlineResult = None,
    minimum_amount_met: bool = True,
    waiting_period_check: WaitingPeriodResult = None,
    exclusion_check: ExclusionCheckResult = None,
    pre_auth_check: PreAuthCheckResult = None,
    limit_checks: LimitChecks = None,
    line_item_results: List[LineItemResult] = None,
    financial_calculation: FinancialCalculation = None,
    overall_decision: Decision = Decision.MANUAL_REVIEW,
) -> Dict[str, Any]:
    result = PolicyEvalResult(
        member_eligible=member_eligible or MemberEligibilityResult(passed=True),
        within_submission_deadline=within_deadline or SubmissionDeadlineResult(passed=True),
        minimum_amount_met=minimum_amount_met,
        waiting_period_check=waiting_period_check or WaitingPeriodResult(passed=True),
        exclusion_check=exclusion_check or ExclusionCheckResult(passed=True),
        pre_auth_check=pre_auth_check or PreAuthCheckResult(passed=True),
        limit_checks=limit_checks or LimitChecks(),
        financial_calculation=financial_calculation or FinancialCalculation(),
        line_item_results=line_item_results or [],
        overall_decision=overall_decision,
        rejection_reasons=rejection_reasons,
    )
    return {**state, "policy_eval_result": result}
