"""Agent 6: Aggregates all agent results into a final ClaimDecision."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models.decision import ClaimDecision, CrossValidationResult, Decision, FraudResult, PolicyEvalResult
from models.document import DocVerificationResult

logger = logging.getLogger(__name__)

# Minimum confidence floor
_MIN_CONFIDENCE = 0.10


async def run_decision_aggregation(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 6 (DecisionAggregation): starting")

    doc_result: Optional[DocVerificationResult] = state.get("doc_verification_result")
    cross_result: Optional[CrossValidationResult] = state.get("cross_validation_result")
    policy_result: Optional[PolicyEvalResult] = state.get("policy_eval_result")
    fraud_result: Optional[FraudResult] = state.get("fraud_result")
    component_failed: bool = state.get("_component_failed", False)
    claimed_amount: float = float(state.get("claimed_amount", 0))

    reasons: List[str] = []
    recommendations: List[str] = []
    errors: List[str] = []
    confidence: float = 1.0

    # ── Collect errors from component failure (TC011) ─────────────────
    if component_failed:
        errors.append("One or more extraction components failed during processing.")
        confidence -= 0.20
        recommendations.append(
            "Manual review recommended: incomplete document extraction due to processing error."
        )

    # ── Priority 1: Document verification failure (TC001, TC002) ─────
    if doc_result and doc_result.status == "failed":
        msg = doc_result.error_message or "Document verification failed."
        reasons.append(msg)
        decision = ClaimDecision(
            decision=Decision.MANUAL_REVIEW,
            approved_amount=0.0,
            confidence_score=max(_MIN_CONFIDENCE, 0.95),
            reasons=reasons,
            recommendations=["Resolve document issues and resubmit."],
            errors=errors,
        )
        logger.info("Agent 6: stopped — doc verification failed")
        return {**state, "final_decision": decision}

    # ── Priority 2: Cross-validation failure (TC003) ──────────────────
    if cross_result and cross_result.status == "failed":
        msg = cross_result.error_message or "Cross-validation failed."
        reasons.append(msg)
        decision = ClaimDecision(
            decision=Decision.MANUAL_REVIEW,
            approved_amount=0.0,
            confidence_score=max(_MIN_CONFIDENCE, 0.90),
            reasons=reasons,
            recommendations=["Ensure all documents belong to the same patient and resubmit."],
            errors=errors,
        )
        logger.info("Agent 6: stopped — cross-validation failed")
        return {**state, "final_decision": decision}

    # ── Confidence modifiers from cross-validation advisories ────────
    if cross_result:
        if not cross_result.amount_match:
            confidence -= 0.05
        if not cross_result.date_match:
            confidence -= 0.05
        if not cross_result.member_name_match:
            confidence -= 0.10
            recommendations.append(
                "Member name on documents does not exactly match policy records — manual verification recommended."
            )

    # ── Priority 3: Fraud → MANUAL_REVIEW (TC009) ────────────────────
    if fraud_result and fraud_result.recommendation == "MANUAL_REVIEW":
        flag_details = "; ".join(f.details for f in fraud_result.flags)
        reasons.append(
            f"Claim flagged for manual review due to suspicious pattern(s): {flag_details}"
        )
        recommendations.append(
            f"Fraud detection signals detected (score: {fraud_result.fraud_score:.2f}). "
            "Claim routed to fraud review team."
        )
        confidence -= 0.25
        decision = ClaimDecision(
            decision=Decision.MANUAL_REVIEW,
            approved_amount=0.0,
            confidence_score=max(_MIN_CONFIDENCE, round(confidence, 2)),
            reasons=reasons,
            recommendations=recommendations,
            errors=errors,
        )
        logger.info("Agent 6: fraud → MANUAL_REVIEW")
        return {**state, "final_decision": decision}

    # ── Priority 4: Policy evaluation result ─────────────────────────
    if not policy_result:
        # No policy evaluation — shouldn't happen in normal flow
        reasons.append("Policy evaluation was not completed.")
        recommendations.append("Manual review required.")
        if component_failed:
            confidence -= 0.20
        decision = ClaimDecision(
            decision=Decision.MANUAL_REVIEW,
            approved_amount=0.0,
            confidence_score=max(_MIN_CONFIDENCE, round(confidence, 2)),
            reasons=reasons,
            recommendations=recommendations,
            errors=errors,
        )
        return {**state, "final_decision": decision}

    # Use policy decision as the primary outcome
    policy_decision = policy_result.overall_decision
    approved_amount = policy_result.financial_calculation.approved_amount
    reasons.extend(policy_result.rejection_reasons)

    # Confidence modifiers based on policy result certainty
    if policy_decision == Decision.REJECTED:
        # Clear policy rejections (exclusion, waiting period, per-claim limit) are HIGH confidence
        rejection_lower = " ".join(r.lower() for r in policy_result.rejection_reasons)
        clear_rejection = any(
            kw in rejection_lower
            for kw in ["exclusion", "excluded", "waiting period", "per-claim limit", "not found"]
        )
        if clear_rejection:
            confidence = 0.95  # Override — clear policy rule rejection is very confident (TC012 needs 0.90+)
        else:
            confidence -= 0.05

    if policy_decision == Decision.APPROVED and not reasons:
        # Build a positive reason
        fin = policy_result.financial_calculation
        breakdown_str = " → ".join(
            f"{b.label}: ₹{abs(b.amount):,.0f}" for b in fin.breakdown
        )
        reasons.append(f"Claim meets all policy criteria. Financial breakdown: {breakdown_str}")

    if policy_decision == Decision.PARTIAL:
        approved_items = [li for li in policy_result.line_item_results if li.status == "approved"]
        rejected_items = [li for li in policy_result.line_item_results if li.status == "rejected"]
        if approved_items:
            reasons.append(
                "Approved items: "
                + ", ".join(f"{li.description} ₹{li.amount:,.0f}" for li in approved_items)
            )
        if rejected_items:
            reasons.append(
                "Rejected items: "
                + ", ".join(f"{li.description} ₹{li.amount:,.0f} ({li.reason})" for li in rejected_items)
            )

    # Component failure advisory (TC011)
    if component_failed and policy_decision == Decision.APPROVED:
        policy_decision = Decision.MANUAL_REVIEW
        reasons.append("Approved by policy logic but routed to manual review due to extraction failure.")
        recommendations.append(
            "Manual review recommended: one or more documents could not be fully extracted."
        )

    # Low confidence catch-all
    if confidence < 0.70:
        recommendations.append(
            f"Low confidence score ({confidence:.0%}) — manual verification recommended."
        )

    final_confidence = max(_MIN_CONFIDENCE, round(confidence, 2))

    decision = ClaimDecision(
        decision=policy_decision,
        approved_amount=approved_amount,
        confidence_score=final_confidence,
        reasons=reasons,
        recommendations=recommendations,
        errors=errors,
    )

    logger.info(
        "Agent 6: decision=%s, approved=%.2f, confidence=%.2f",
        policy_decision.value, approved_amount, final_confidence,
    )
    return {**state, "final_decision": decision}
