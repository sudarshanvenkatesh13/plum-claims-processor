"""Integration tests for the full claims pipeline."""
from __future__ import annotations

import json
from datetime import date

import pytest


@pytest.fixture
def pipeline_with_policy(sample_policy, tmp_path, monkeypatch):
    from pathlib import Path
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(sample_policy))
    monkeypatch.setattr("config.settings.POLICY_FILE_PATH", str(policy_file))

    # Re-import after patching so ClaimsPipeline picks up the correct path
    import importlib
    import orchestrator.pipeline as pipeline_mod
    importlib.reload(pipeline_mod)
    # Reset the compiled graph cache so the new pipeline module is used
    pipeline_mod._COMPILED_GRAPH = None
    return pipeline_mod.ClaimsPipeline()


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
    async def test_result_has_decision_when_completed(self, pipeline_with_policy, sample_submission):
        result = await pipeline_with_policy.process(sample_submission)
        if result.status == "completed":
            assert result.decision in ("APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW")

    @pytest.mark.asyncio
    async def test_wrong_documents_stops_early(self, pipeline_with_policy):
        """TC001: Two prescriptions for CONSULTATION (needs PRESCRIPTION + HOSPITAL_BILL)."""
        from models.claim import ClaimSubmission, ClaimCategory, UploadedDocument
        submission = ClaimSubmission(
            member_id="MEM-001",
            policy_id="POL-001",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=date(2026, 4, 1),
            claimed_amount=1500.0,
            documents=[
                UploadedDocument(file_id="d1", file_name="rx1.jpg", actual_type="PRESCRIPTION", quality="GOOD"),
                UploadedDocument(file_id="d2", file_name="rx2.jpg", actual_type="PRESCRIPTION", quality="GOOD"),
            ],
        )
        result = await pipeline_with_policy.process(submission)
        assert result.status == "stopped_early"
        assert result.error_message is not None
        assert "Hospital Bill" in result.error_message or "HOSPITAL_BILL" in result.error_message

    @pytest.mark.asyncio
    async def test_unreadable_doc_stops_early(self, pipeline_with_policy):
        """TC002: Unreadable pharmacy bill stops pipeline."""
        from models.claim import ClaimSubmission, ClaimCategory, UploadedDocument
        submission = ClaimSubmission(
            member_id="MEM-001",
            policy_id="POL-001",
            claim_category=ClaimCategory.PHARMACY,
            treatment_date=date(2026, 4, 1),
            claimed_amount=500.0,
            documents=[
                UploadedDocument(file_id="d1", file_name="rx.jpg", actual_type="PRESCRIPTION", quality="GOOD"),
                UploadedDocument(file_id="d2", file_name="bill.jpg", actual_type="PHARMACY_BILL", quality="UNREADABLE"),
            ],
        )
        result = await pipeline_with_policy.process(submission)
        assert result.status == "stopped_early"
        assert "unreadable" in (result.error_message or "").lower()
