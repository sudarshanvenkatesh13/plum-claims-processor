"""Tests for Agent 4: PolicyEvaluation (pure logic, no LLM)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from services.policy_loader import PolicyLoader
from models.claim import ClaimCategory


@pytest.fixture
def policy_loader(sample_policy, tmp_path):
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(sample_policy))
    return PolicyLoader(str(policy_file))


class TestMemberLookup:
    def test_existing_member(self, policy_loader):
        member = policy_loader.get_member("MEM-001")
        assert member is not None
        assert member.name == "Rahul Sharma"

    def test_missing_member(self, policy_loader):
        assert policy_loader.get_member("NONEXISTENT") is None


class TestDocumentRequirements:
    def test_consultation_requires_prescription(self, policy_loader):
        reqs = policy_loader.get_document_requirements("CONSULTATION")
        assert "PRESCRIPTION" in reqs["required"]

    def test_unknown_category_returns_empty(self, policy_loader):
        reqs = policy_loader.get_document_requirements("UNKNOWN_CATEGORY")
        assert reqs["required"] == []
        assert reqs["optional"] == []


class TestCategoryConfig:
    def test_consultation_copay(self, policy_loader):
        config = policy_loader.get_category_config("CONSULTATION")
        assert config["copay_percent"] == pytest.approx(10)

    def test_consultation_sub_limit(self, policy_loader):
        config = policy_loader.get_category_config("CONSULTATION")
        assert config["sub_limit"] == 5000


class TestWaitingPeriod:
    def test_condition_specific_waiting_period(self, policy_loader):
        _, days = policy_loader.get_waiting_period_for_diagnosis("diabetes mellitus")
        assert days == 90

    def test_initial_waiting_period_fallback(self, policy_loader):
        _, days = policy_loader.get_waiting_period_for_diagnosis("unknown condition xyz")
        assert days == 30

    def test_initial_waiting_period_direct(self, policy_loader):
        assert policy_loader.get_initial_waiting_period() == 30


class TestNetworkHospital:
    def test_network_hospital_match(self, policy_loader):
        assert policy_loader.is_network_hospital("Apollo Hospital") is True

    def test_partial_match(self, policy_loader):
        assert policy_loader.is_network_hospital("Apollo Hospital Chennai") is True

    def test_non_network_hospital(self, policy_loader):
        assert policy_loader.is_network_hospital("Unknown Clinic") is False

    def test_empty_name(self, policy_loader):
        assert policy_loader.is_network_hospital("") is False


class TestExclusions:
    def test_excluded_condition(self, policy_loader):
        assert policy_loader.is_excluded_condition("cosmetic surgery") is True

    def test_non_excluded_condition(self, policy_loader):
        assert policy_loader.is_excluded_condition("fever and cold") is False

    def test_excluded_procedure_dental(self, policy_loader):
        # Dental excluded procedures live in opd_categories.dental.excluded_procedures
        cat_excl = policy_loader.get_category_exclusions("DENTAL")
        assert any("whitening" in e.lower() for e in cat_excl)

    def test_non_excluded_procedure(self, policy_loader):
        assert policy_loader.is_excluded_procedure("DENTAL", "root canal") is False


class TestFraudThresholds:
    def test_fraud_thresholds_loaded(self, policy_loader):
        thresholds = policy_loader.get_fraud_thresholds()
        assert thresholds["high_value_claim_threshold"] == 20000
        assert thresholds["same_day_claims_limit"] == 2


class TestSubmissionRules:
    def test_submission_deadline(self, policy_loader):
        assert policy_loader.get_submission_deadline_days() == 90

    def test_minimum_claim_amount(self, policy_loader):
        assert policy_loader.get_minimum_claim_amount() == 200


class TestPolicyEvaluationAgent:
    @pytest.mark.asyncio
    async def test_returns_approved_for_valid_claim(self, sample_policy, tmp_path):
        from agents.policy_evaluation import run_policy_evaluation
        from models.decision import Decision
        from services.policy_loader import PolicyLoader

        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(sample_policy))
        pl = PolicyLoader(str(policy_file))

        state = {
            "claim_id": "CLM-TEST",
            "claimed_amount": 500.0,
            "claim_category": "CONSULTATION",
            "member_id": "MEM-001",
            "treatment_date": date(2026, 4, 1),
            "hospital_name": None,
            "ytd_claims_amount": 0.0,
            "extraction_results": [],
            "diagnosis": None,
            "policy_loader": pl,
        }
        result_state = await run_policy_evaluation(state)
        assert "policy_eval_result" in result_state
        assert result_state["policy_eval_result"].overall_decision == Decision.APPROVED
