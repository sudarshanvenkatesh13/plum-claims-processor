"""Tests for Agent 4: PolicyEvaluation (pure logic, no LLM)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta

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
        assert config["copay"] == pytest.approx(0.1)

    def test_consultation_sub_limit(self, policy_loader):
        config = policy_loader.get_category_config("CONSULTATION")
        assert config["sub_limit"] == 5000


class TestWaitingPeriod:
    def test_condition_specific_waiting_period(self, policy_loader):
        days = policy_loader.get_waiting_period("diabetes")
        assert days == 365

    def test_initial_waiting_period_fallback(self, policy_loader):
        days = policy_loader.get_waiting_period("unknown_condition")
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

    def test_excluded_procedure(self, policy_loader):
        assert policy_loader.is_excluded_procedure("DENTAL", "teeth whitening") is True

    def test_non_excluded_procedure(self, policy_loader):
        assert policy_loader.is_excluded_procedure("DENTAL", "root canal") is False


class TestFraudThresholds:
    def test_fraud_thresholds_loaded(self, policy_loader):
        thresholds = policy_loader.get_fraud_thresholds()
        assert thresholds["high_value_threshold"] == 20000
        assert thresholds["same_day_limit"] == 2


class TestSubmissionRules:
    def test_submission_deadline(self, policy_loader):
        assert policy_loader.get_submission_deadline_days() == 90

    def test_minimum_claim_amount(self, policy_loader):
        assert policy_loader.get_minimum_claim_amount() == 200


class TestPolicyEvaluationAgent:
    @pytest.mark.asyncio
    async def test_placeholder_returns_approved(self, sample_submission):
        from agents.policy_evaluation import run_policy_evaluation
        from models.decision import Decision

        state = {
            "claim_id": "CLM-TEST",
            "claimed_amount": sample_submission.claimed_amount,
            "claim_category": sample_submission.claim_category.value,
            "member_id": sample_submission.member_id,
        }
        result_state = await run_policy_evaluation(state)
        assert "policy_eval_result" in result_state
        assert result_state["policy_eval_result"].overall_decision == Decision.APPROVED
