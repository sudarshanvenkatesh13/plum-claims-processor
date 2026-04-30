"""Tests for Agent 5: FraudDetection."""
from __future__ import annotations

from datetime import date

import pytest


class TestFraudDetectionAgent:
    @pytest.mark.asyncio
    async def test_clean_claim_is_clear(self):
        from agents.fraud_detection import run_fraud_detection

        state = {
            "claim_id": "CLM-TEST",
            "claimed_amount": 3500.0,
            "treatment_date": date(2026, 4, 1),
            "claims_history": [],
            "ytd_claims_amount": 0.0,
            "policy_loader": None,
        }
        result_state = await run_fraud_detection(state)
        assert "fraud_result" in result_state
        fraud = result_state["fraud_result"]
        assert fraud.fraud_score < 0.5
        assert fraud.recommendation == "CLEAR"

    @pytest.mark.asyncio
    async def test_returns_fraud_result_fields(self):
        from agents.fraud_detection import run_fraud_detection

        state = {
            "claim_id": "CLM-001",
            "claimed_amount": 50000.0,
            "treatment_date": date(2026, 4, 1),
            "claims_history": [],
            "ytd_claims_amount": 200000.0,
            "policy_loader": None,
        }
        result_state = await run_fraud_detection(state)
        fraud = result_state["fraud_result"]
        assert hasattr(fraud, "fraud_score")
        assert hasattr(fraud, "flags")
        assert hasattr(fraud, "same_day_count")
        assert hasattr(fraud, "monthly_count")
        assert hasattr(fraud, "is_high_value")
        assert hasattr(fraud, "recommendation")

    @pytest.mark.asyncio
    async def test_fraud_score_within_range(self):
        from agents.fraud_detection import run_fraud_detection

        state = {
            "claim_id": "CLM-002",
            "claimed_amount": 1000.0,
            "treatment_date": date(2026, 4, 1),
            "claims_history": [],
            "ytd_claims_amount": 0.0,
            "policy_loader": None,
        }
        result_state = await run_fraud_detection(state)
        fraud = result_state["fraud_result"]
        assert 0.0 <= fraud.fraud_score <= 1.0

    @pytest.mark.asyncio
    async def test_same_day_violation_routes_to_manual_review(self):
        """TC009: 3 prior claims today (limit=2) → MANUAL_REVIEW."""
        from agents.fraud_detection import run_fraud_detection
        from models.claim import PriorClaim

        treatment_date = date(2026, 4, 1)
        prior_claims = [
            PriorClaim(claim_id=f"C{i}", date=treatment_date, amount=1000, provider="P")
            for i in range(3)
        ]
        state = {
            "claim_id": "CLM-009",
            "claimed_amount": 1500.0,
            "treatment_date": treatment_date,
            "claims_history": prior_claims,
            "ytd_claims_amount": 3000.0,
            "policy_loader": None,
        }
        result_state = await run_fraud_detection(state)
        fraud = result_state["fraud_result"]
        assert fraud.recommendation == "MANUAL_REVIEW"
        assert fraud.same_day_count == 3
        assert any(f.flag_type == "MULTIPLE_SAME_DAY_CLAIMS" for f in fraud.flags)
