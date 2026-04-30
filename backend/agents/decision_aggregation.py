"""Agent 6: Aggregates all agent results into a final decision + builds DecisionTrace."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_decision_aggregation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder — will be implemented in the next phase.

    Aggregates:
    - doc_verification_result
    - extraction_results
    - cross_validation_result
    - policy_eval_result
    - fraud_result

    Produces:
    - Final Decision (APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW)
    - approved_amount
    - confidence_score
    - reasons list
    - recommendations list
    - errors list
    """
    logger.info("Agent 6 (DecisionAggregation): placeholder invoked")
    from models.decision import ClaimDecision, Decision

    policy_result = state.get("policy_eval_result")
    fraud_result = state.get("fraud_result")

    decision = Decision.APPROVED
    approved_amount = state.get("claimed_amount", 0.0)
    confidence = 0.80
    reasons: list = ["Placeholder decision — full logic not yet implemented"]
    recommendations: list = []

    if policy_result:
        decision = policy_result.overall_decision
        approved_amount = policy_result.financial_calculation.approved_amount
        reasons = policy_result.rejection_reasons or ["Claim meets policy criteria"]

    if fraud_result and fraud_result.fraud_score > 0.7:
        decision = Decision.MANUAL_REVIEW
        reasons.append("High fraud score — flagged for manual review")
        confidence = max(0.3, confidence - fraud_result.fraud_score)

    final = ClaimDecision(
        decision=decision,
        approved_amount=approved_amount,
        confidence_score=confidence,
        reasons=reasons,
        recommendations=recommendations,
    )
    return {**state, "final_decision": final}
