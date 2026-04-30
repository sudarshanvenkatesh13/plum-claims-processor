from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure backend root is on sys.path when running tests from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set dummy env vars before importing settings
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fixture")


@pytest.fixture
def sample_policy() -> Dict[str, Any]:
    return {
        "policy_id": "POL-001",
        "policy_name": "Test Policy",
        "members": [
            {
                "member_id": "MEM-001",
                "name": "Rahul Sharma",
                "age": 35,
                "gender": "M",
                "relationship": "self",
                "pre_existing_conditions": [],
            }
        ],
        "coverage": {
            "annual_limit": 300000,
            "per_claim_limit": 50000,
        },
        "opd_categories": {
            "CONSULTATION": {"sub_limit": 5000, "copay": 0.1, "network_discount": 0.15},
            "DIAGNOSTIC": {"sub_limit": 10000, "copay": 0.0, "network_discount": 0.10},
            "PHARMACY": {"sub_limit": 8000, "copay": 0.2, "network_discount": 0.0},
        },
        "document_requirements": {
            "CONSULTATION": {
                "required": ["PRESCRIPTION"],
                "optional": ["HOSPITAL_BILL"],
            },
            "DIAGNOSTIC": {
                "required": ["LAB_REPORT", "PRESCRIPTION"],
                "optional": ["DIAGNOSTIC_REPORT"],
            },
            "PHARMACY": {
                "required": ["PHARMACY_BILL", "PRESCRIPTION"],
                "optional": [],
            },
        },
        "waiting_periods": {
            "initial_waiting_period_days": 30,
            "condition_specific": {
                "diabetes": 365,
                "hypertension": 365,
                "knee replacement": 730,
            },
        },
        "exclusions": {
            "general": ["cosmetic", "dental whitening", "hair transplant"],
            "category_specific": {
                "DENTAL": ["teeth whitening", "cosmetic fillings"],
            },
        },
        "pre_authorization": {
            "required_for": ["hospitalization", "surgery"],
            "threshold_amount": 25000,
        },
        "network_hospitals": [
            "Apollo Hospital",
            "Fortis Healthcare",
            "Max Hospital",
        ],
        "fraud_thresholds": {
            "high_value_threshold": 20000,
            "same_day_limit": 2,
            "monthly_frequency_limit": 5,
        },
        "submission_rules": {
            "submission_deadline_days": 90,
            "minimum_claim_amount": 200,
        },
    }


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
                file_content="base64encodedcontent==",
            )
        ],
        ytd_claims_amount=15000.0,
    )
