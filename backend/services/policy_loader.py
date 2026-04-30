from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.policy import MemberInfo

logger = logging.getLogger(__name__)

# Maps policy JSON condition keys to lists of keywords found in free-text diagnoses.
_CONDITION_KEYWORD_MAP: Dict[str, List[str]] = {
    "diabetes": ["diabetes", "t2dm", "dm ", "diabetic", "diabetes mellitus", "type 2 diabetes", "type ii diabetes"],
    "hypertension": ["hypertension", "htn", "high blood pressure", "hypertensive"],
    "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid", "hashimoto", "goitre"],
    "obesity_treatment": ["obesity", "bariatric", "weight loss program", "morbid obese", "obese"],
    "joint_replacement": ["joint replacement", "knee replacement", "hip replacement", "arthroplasty"],
    "maternity": ["maternity", "pregnancy", "antenatal", "prenatal", "obstetric", "delivery"],
    "mental_health": ["mental health", "depression", "anxiety disorder", "psychiatric", "bipolar"],
    "hernia": ["hernia", "herniation"],
    "cataract": ["cataract"],
}


class PolicyLoader:
    def __init__(self, policy_file_path: str) -> None:
        self._path = Path(policy_file_path)
        self._data: Dict[str, Any] = {}
        self._members: Dict[str, MemberInfo] = {}
        self._members_raw: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Policy file not found at %s — using empty policy", self._path)
            return
        with self._path.open("r", encoding="utf-8") as fh:
            self._data = json.load(fh)
        self._index_members()
        logger.info("Policy loaded from %s", self._path)

    def _index_members(self) -> None:
        for raw in self._data.get("members", []):
            mid = raw.get("member_id")
            if not mid:
                continue
            self._members_raw[mid] = raw
            try:
                m = MemberInfo(**raw)
                self._members[mid] = m
            except Exception as exc:
                logger.warning("Could not parse member %s: %s — using raw dict fallback", mid, exc)

    # ------------------------------------------------------------------
    # Member accessors
    # ------------------------------------------------------------------

    def get_member(self, member_id: str) -> Optional[MemberInfo]:
        return self._members.get(member_id)

    def get_member_raw(self, member_id: str) -> Optional[Dict[str, Any]]:
        return self._members_raw.get(member_id)

    def get_all_members(self) -> List[MemberInfo]:
        return list(self._members.values())

    def get_member_join_date(self, member_id: str) -> Optional[str]:
        raw = self._members_raw.get(member_id, {})
        return raw.get("join_date")

    # ------------------------------------------------------------------
    # Document requirements
    # ------------------------------------------------------------------

    def get_document_requirements(self, category: str) -> Dict[str, List[str]]:
        """category should be UPPERCASE (matches JSON keys)."""
        doc_reqs = self._data.get("document_requirements", {})
        cat_reqs = doc_reqs.get(category.upper(), {})
        return {
            "required": cat_reqs.get("required", []),
            "optional": cat_reqs.get("optional", []),
        }

    # ------------------------------------------------------------------
    # Category config — JSON uses lowercase keys
    # ------------------------------------------------------------------

    def get_category_config(self, category: str) -> Dict[str, Any]:
        categories = self._data.get("opd_categories", {})
        return categories.get(category.lower()) or categories.get(category) or {}

    def get_all_categories(self) -> Dict[str, Any]:
        return self._data.get("opd_categories", {})

    def get_category_exclusions(self, category: str) -> List[str]:
        cat = self.get_category_config(category)
        return (
            cat.get("excluded_procedures")
            or cat.get("excluded_items")
            or cat.get("excluded")
            or []
        )

    def get_category_covered_procedures(self, category: str) -> List[str]:
        cat = self.get_category_config(category)
        return (
            cat.get("covered_procedures")
            or cat.get("covered_items")
            or cat.get("covered_systems")
            or []
        )

    # ------------------------------------------------------------------
    # Waiting periods — JSON uses "specific_conditions" key
    # ------------------------------------------------------------------

    def get_initial_waiting_period(self) -> int:
        return int(self._data.get("waiting_periods", {}).get("initial_waiting_period_days", 0))

    def get_waiting_period(self, condition_key: str) -> Optional[int]:
        """Look up by exact condition key (e.g. 'diabetes')."""
        waiting = self._data.get("waiting_periods", {})
        specific = waiting.get("specific_conditions") or waiting.get("condition_specific", {})
        val = specific.get(condition_key)
        if val is None:
            return waiting.get("initial_waiting_period_days")
        return int(val)

    def get_waiting_period_for_diagnosis(self, diagnosis: str) -> Tuple[Optional[str], int]:
        """
        Fuzzy-match free-text diagnosis against condition keywords.
        Returns (matched_condition_key, waiting_days).
        Falls back to initial waiting period if no specific match.
        """
        initial = self.get_initial_waiting_period()
        if not diagnosis:
            return None, initial

        diag_lower = diagnosis.lower()
        waiting = self._data.get("waiting_periods", {})
        specific = waiting.get("specific_conditions") or waiting.get("condition_specific", {})

        for condition_key, keywords in _CONDITION_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in diag_lower:
                    days = int(specific.get(condition_key, initial))
                    return condition_key, days

        return None, initial

    # ------------------------------------------------------------------
    # Exclusions — JSON uses "conditions" list (not "general")
    # ------------------------------------------------------------------

    def get_excluded_conditions_list(self) -> List[str]:
        excl = self._data.get("exclusions", {})
        return excl.get("conditions") or excl.get("general", [])

    _STOP_WORDS = frozenset({"and", "or", "for", "the", "a", "an", "of", "in", "on", "at", "to", "with", "by", "non"})

    def is_excluded_condition(self, text: str) -> bool:
        """Check if text (diagnosis, procedure) matches any general exclusion."""
        if not text:
            return False
        exclusions = self.get_excluded_conditions_list()
        text_lower = text.lower()
        for excl in exclusions:
            excl_lower = excl.lower()
            if excl_lower in text_lower or text_lower in excl_lower:
                return True
            # Meaningful word overlap: any shared word >= 5 chars that isn't a stop word
            excl_words = set(excl_lower.split()) - self._STOP_WORDS
            text_words = set(text_lower.split()) - self._STOP_WORDS
            meaningful = excl_words & text_words
            if meaningful and any(len(w) >= 5 for w in meaningful):
                return True
        return False

    def get_matching_exclusion(self, text: str) -> Optional[str]:
        """Returns the matched exclusion string, or None. Uses same logic as is_excluded_condition."""
        if not text:
            return None
        exclusions = self.get_excluded_conditions_list()
        text_lower = text.lower()
        for excl in exclusions:
            excl_lower = excl.lower()
            if excl_lower in text_lower or text_lower in excl_lower:
                return excl
            excl_words = set(excl_lower.split()) - self._STOP_WORDS
            text_words = set(text_lower.split()) - self._STOP_WORDS
            meaningful = excl_words & text_words
            if meaningful and any(len(w) >= 5 for w in meaningful):
                return excl
        return None

    def is_excluded_procedure(self, category: str, procedure: str) -> bool:
        """Check procedure against category-specific exclusions."""
        if not procedure:
            return False
        cat_exclusions = self.get_category_exclusions(category)
        proc_lower = procedure.lower()
        for excl in cat_exclusions:
            if excl.lower() in proc_lower or proc_lower in excl.lower():
                return True
        return False

    def get_exclusions(self) -> Dict[str, Any]:
        return self._data.get("exclusions", {})

    # ------------------------------------------------------------------
    # Limits — JSON uses "annual_opd_limit" and "deadline_days_from_treatment"
    # ------------------------------------------------------------------

    def get_annual_limit(self) -> float:
        coverage = self._data.get("coverage", {})
        val = coverage.get("annual_opd_limit") or coverage.get("annual_limit", 0)
        return float(val)

    def get_per_claim_limit(self) -> float:
        return float(self._data.get("coverage", {}).get("per_claim_limit", 0))

    def get_minimum_claim_amount(self) -> float:
        return float(self._data.get("submission_rules", {}).get("minimum_claim_amount", 0))

    def get_submission_deadline_days(self) -> int:
        rules = self._data.get("submission_rules", {})
        val = rules.get("deadline_days_from_treatment") or rules.get("submission_deadline_days", 30)
        return int(val)

    # ------------------------------------------------------------------
    # Network / fraud / pre-auth
    # ------------------------------------------------------------------

    def is_network_hospital(self, hospital_name: str) -> bool:
        if not hospital_name:
            return False
        hospitals: List[str] = self._data.get("network_hospitals", [])
        hospital_lower = hospital_name.lower()
        return any(h.lower() in hospital_lower or hospital_lower in h.lower() for h in hospitals)

    def get_network_hospitals(self) -> List[str]:
        return self._data.get("network_hospitals", [])

    def get_fraud_thresholds(self) -> Dict[str, Any]:
        return self._data.get("fraud_thresholds", {})

    def get_submission_rules(self) -> Dict[str, Any]:
        return self._data.get("submission_rules", {})

    def get_pre_auth_rules(self) -> Dict[str, Any]:
        return self._data.get("pre_authorization", {})

    def raw(self) -> Dict[str, Any]:
        return self._data
