"""Agent 5: Fraud detection via pattern analysis of claim history."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

from models.decision import FraudFlag, FraudResult

logger = logging.getLogger(__name__)


async def run_fraud_detection(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 5 (FraudDetection): starting")

    policy_loader = state.get("policy_loader")
    treatment_date: date = state.get("treatment_date", date.today())
    claimed_amount: float = float(state.get("claimed_amount", 0))
    claims_history: List[Any] = state.get("claims_history") or []

    thresholds = policy_loader.get_fraud_thresholds() if policy_loader else {}
    same_day_limit: int = int(thresholds.get("same_day_claims_limit", 2))
    monthly_limit: int = int(thresholds.get("monthly_claims_limit", 6))
    high_value_threshold: float = float(thresholds.get("high_value_claim_threshold", 25000))
    score_manual_review_threshold: float = float(thresholds.get("fraud_score_manual_review_threshold", 0.80))

    flags: List[FraudFlag] = []
    fraud_score: float = 0.0

    # ── 1. Same-day claims count ──────────────────────────────────────
    # Count prior claims on the SAME treatment date (TC009: 3 prior + this = 4 total)
    same_day_count = sum(
        1 for c in claims_history
        if _claim_date(c) == treatment_date
    )
    if same_day_count >= same_day_limit:
        flags.append(
            FraudFlag(
                flag_type="MULTIPLE_SAME_DAY_CLAIMS",
                details=(
                    f"{same_day_count} previous claims found on {treatment_date.isoformat()} "
                    f"(limit is {same_day_limit} per day). This is claim #{same_day_count + 1} today."
                ),
                severity="high",
            )
        )
        fraud_score = min(1.0, fraud_score + 0.5)

    # ── 2. Monthly claims frequency ──────────────────────────────────
    monthly_count = sum(
        1 for c in claims_history
        if _claim_date(c) is not None
        and _claim_date(c).year == treatment_date.year
        and _claim_date(c).month == treatment_date.month
    )
    if monthly_count >= monthly_limit:
        flags.append(
            FraudFlag(
                flag_type="EXCESSIVE_MONTHLY_CLAIMS",
                details=(
                    f"{monthly_count} claims already filed this month "
                    f"(limit is {monthly_limit} per month)."
                ),
                severity="medium",
            )
        )
        fraud_score = min(1.0, fraud_score + 0.3)

    # ── 3. High-value claim ───────────────────────────────────────────
    is_high_value = claimed_amount > high_value_threshold
    if is_high_value:
        flags.append(
            FraudFlag(
                flag_type="HIGH_VALUE_CLAIM",
                details=(
                    f"Claimed amount ₹{claimed_amount:,.0f} exceeds high-value threshold "
                    f"of ₹{high_value_threshold:,.0f}."
                ),
                severity="medium",
            )
        )
        fraud_score = min(1.0, fraud_score + 0.2)

    # ── 4. Round-number amount (weak signal) ─────────────────────────
    if claimed_amount > 1000 and claimed_amount % 1000 == 0:
        flags.append(
            FraudFlag(
                flag_type="ROUND_AMOUNT",
                details=f"Claimed amount ₹{claimed_amount:,.0f} is a round number — minor signal.",
                severity="low",
            )
        )
        fraud_score = min(1.0, fraud_score + 0.05)

    # ── 5. Determine recommendation ──────────────────────────────────
    # Same-day limit violation alone is enough to route to MANUAL_REVIEW (strong fraud signal)
    same_day_violated = any(f.flag_type == "MULTIPLE_SAME_DAY_CLAIMS" for f in flags)
    if same_day_violated or fraud_score >= score_manual_review_threshold:
        recommendation = "MANUAL_REVIEW"
    else:
        recommendation = "CLEAR"

    result = FraudResult(
        fraud_score=round(fraud_score, 3),
        flags=flags,
        same_day_count=same_day_count,
        monthly_count=monthly_count,
        is_high_value=is_high_value,
        recommendation=recommendation,
    )

    logger.info(
        "Agent 5: fraud_score=%.3f, flags=%d, recommendation=%s",
        fraud_score, len(flags), recommendation,
    )
    return {**state, "fraud_result": result}


def _claim_date(claim: Any):
    """Safely extract date from a PriorClaim object or dict."""
    if claim is None:
        return None
    if hasattr(claim, "date"):
        return claim.date
    if isinstance(claim, dict):
        raw = claim.get("date")
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None
    return None
