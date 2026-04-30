from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fixture")


@pytest.fixture
def sample_policy() -> Dict[str, Any]:
    """Minimal policy that mirrors the real policy_terms.json structure."""
    return {
        "policy_id": "POL-001",
        "policy_name": "Test Policy",
        "coverage": {
            "annual_opd_limit": 300000,
            "per_claim_limit": 50000,
        },
        "opd_categories": {
            "consultation": {
                "sub_limit": 5000,
                "copay_percent": 10,
                "network_discount_percent": 20,
            },
            "diagnostic": {
                "sub_limit": 10000,
                "copay_percent": 0,
                "network_discount_percent": 10,
                "pre_auth_threshold": 10000,
                "high_value_tests_requiring_pre_auth": ["MRI", "CT Scan", "PET Scan"],
            },
            "pharmacy": {
                "sub_limit": 8000,
                "copay_percent": 0,
            },
            "dental": {
                "sub_limit": 10000,
                "copay_percent": 0,
                "covered_procedures": ["Root Canal Treatment", "Tooth Extraction"],
                "excluded_procedures": ["Teeth Whitening", "Cosmetic Fillings"],
            },
        },
        "document_requirements": {
            "CONSULTATION": {
                "required": ["PRESCRIPTION", "HOSPITAL_BILL"],
                "optional": [],
            },
            "DIAGNOSTIC": {
                "required": ["LAB_REPORT", "PRESCRIPTION"],
                "optional": ["DIAGNOSTIC_REPORT"],
            },
            "PHARMACY": {
                "required": ["PHARMACY_BILL", "PRESCRIPTION"],
                "optional": [],
            },
            "DENTAL": {
                "required": ["HOSPITAL_BILL"],
                "optional": ["DENTAL_REPORT"],
            },
        },
        "waiting_periods": {
            "initial_waiting_period_days": 30,
            "specific_conditions": {
                "diabetes": 90,
                "hypertension": 90,
            },
        },
        "exclusions": {
            "conditions": ["Cosmetic procedures", "Hair transplant", "Obesity and weight loss programs"],
        },
        "pre_authorization": {
            "required_for": ["MRI scan (amount > ₹10,000)"],
            "validity_days": 30,
        },
        "network_hospitals": ["Apollo Hospital", "Fortis Healthcare", "Max Hospital"],
        "fraud_thresholds": {
            "high_value_claim_threshold": 20000,
            "same_day_claims_limit": 2,
            "monthly_claims_limit": 5,
            "fraud_score_manual_review_threshold": 0.80,
        },
        "submission_rules": {
            "deadline_days_from_treatment": 90,
            "minimum_claim_amount": 200,
        },
        "members": [
            {
                "member_id": "MEM-001",
                "name": "Rahul Sharma",
                "date_of_birth": "1985-03-15",
                "gender": "M",
                "relationship": "SELF",
                "join_date": "2024-01-01",
            }
        ],
    }


@pytest.fixture
def policy_loader_fixture(sample_policy, tmp_path):
    from services.policy_loader import PolicyLoader
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(sample_policy))
    return PolicyLoader(str(policy_file))


@pytest.fixture
def sample_submission():
    from models.claim import ClaimSubmission, ClaimCategory, UploadedDocument
    return ClaimSubmission(
        member_id="MEM-001",
        policy_id="POL-001",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2026, 4, 1),
        claimed_amount=3500.0,
        hospital_name="Apollo Hospital",
        documents=[
            UploadedDocument(
                file_id="doc-001",
                file_name="prescription.jpg",
                file_content="",
                actual_type="PRESCRIPTION",
                quality="GOOD",
            ),
            UploadedDocument(
                file_id="doc-002",
                file_name="bill.jpg",
                file_content="",
                actual_type="HOSPITAL_BILL",
                quality="GOOD",
            ),
        ],
        ytd_claims_amount=15000.0,
    )
