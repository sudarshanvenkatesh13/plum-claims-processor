"""Integration tests for the full claims pipeline."""
from __future__ import annotations

import json
import os
from datetime import date

import pytest


@pytest.fixture
def pipeline_with_policy(sample_policy, tmp_path, monkeypatch):
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(sample_policy))
    monkeypatch.setenv("POLICY_FILE_PATH", str(policy_file))

    from orchestrator.pipeline import ClaimsPipeline
    return ClaimsPipeline()


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_returns_claim_response(self, pipeline_with_policy, sample_submission):
        result = await pipeline_with_policy.process(sample_submission)
        assert result.claim_id.startswith("CLM-")
        assert result.status in ("completed", "stopped_early")
        assert result.confidence_score >= 0.0
        assert result.trace is not None

    @pytest.mark.asyncio
    async def test_pipeline_has_trace_entries(self, pipeline_with_policy, sample_submission):
        result = await pipeline_with_policy.process(sample_submission)
        assert result.trace is not None
        assert len(result.trace.entries) > 0

    @pytest.mark.asyncio
    async def test_pipeline_all_agents_run(self, pipeline_with_policy, sample_submission):
        result = await pipeline_with_policy.process(sample_submission)
        agent_names = {e.agent_name for e in result.trace.entries}
        expected = {
            "DocumentVerification",
            "DocumentExtraction",
            "CrossValidation",
            "PolicyEvaluation",
            "FraudDetection",
            "DecisionAggregation",
        }
        assert expected.issubset(agent_names)

    @pytest.mark.asyncio
    async def test_no_documents_stops_early(self, pipeline_with_policy):
        from models.claim import ClaimSubmission, ClaimCategory
        submission = ClaimSubmission(
            member_id="MEM-001",
            policy_id="POL-001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=date(2026, 4, 1),
            claimed_amount=1000.0,
            documents=[],
        )
        result = await pipeline_with_policy.process(submission)
        assert result.status == "stopped_early"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_result_has_decision(self, pipeline_with_policy, sample_submission):
        result = await pipeline_with_policy.process(sample_submission)
        if result.status == "completed":
            assert result.decision in ("APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW")
