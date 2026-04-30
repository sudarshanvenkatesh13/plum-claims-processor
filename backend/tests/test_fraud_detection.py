"""Tests for Agent 5: FraudDetection."""
from __future__ import annotations

from datetime import date

import pytest


class TestFraudDetectionAgent:
    @pytest.mark.asyncio
    async def test_placeholder_low_fraud_score(self):
        from agents.fraud_detection import run_fraud_detection

        state = {
            "claim_id": "CLM-TEST",
            "claimed_amount": 3500.0,
            "claims_history": [],
            "ytd_claims_amount": 0.0,
        }
        result_state = await run_fraud_detection(state)
        assert "fraud_result" in result_state
        fraud = result_state["fraud_result"]
        assert fraud.fraud_score < 0.5
        assert fraud.recommendation == "proceed"

    @pytest.mark.asyncio
    async def test_placeholder_returns_fraud_result_fields(self):
        from agents.fraud_detection import run_fraud_detection

        state = {"claim_id": "CLM-001", "claimed_amount": 50000.0, "claims_history": [], "ytd_claims_amount": 200000.0}
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

        state = {"claim_id": "CLM-002", "claimed_amount": 1000.0, "claims_history": [], "ytd_claims_amount": 0.0}
        result_state = await run_fraud_detection(state)
        fraud = result_state["fraud_result"]
        assert 0.0 <= fraud.fraud_score <= 1.0
