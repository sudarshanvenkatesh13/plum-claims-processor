from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.policy import MemberInfo

logger = logging.getLogger(__name__)


class PolicyLoader:
    def __init__(self, policy_file_path: str) -> None:
        self._path = Path(policy_file_path)
        self._data: Dict[str, Any] = {}
        self._members: Dict[str, MemberInfo] = {}
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
            try:
                m = MemberInfo(**raw)
                self._members[m.member_id] = m
            except Exception as exc:
                logger.warning("Could not parse member record %s: %s", raw, exc)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_member(self, member_id: str) -> Optional[MemberInfo]:
        return self._members.get(member_id)

    def get_all_members(self) -> List[MemberInfo]:
        return list(self._members.values())

    def get_document_requirements(self, category: str) -> Dict[str, List[str]]:
        doc_reqs = self._data.get("document_requirements", {})
        cat_reqs = doc_reqs.get(category, {})
        return {
            "required": cat_reqs.get("required", []),
            "optional": cat_reqs.get("optional", []),
        }

    def get_category_config(self, category: str) -> Dict[str, Any]:
        categories = self._data.get("opd_categories", {})
        return categories.get(category, {})

    def get_waiting_period(self, condition: str) -> Optional[int]:
        waiting = self._data.get("waiting_periods", {})
        specific = waiting.get("condition_specific", {})
        return specific.get(condition, waiting.get("initial_waiting_period_days"))

    def get_initial_waiting_period(self) -> int:
        return self._data.get("waiting_periods", {}).get("initial_waiting_period_days", 0)

    def is_network_hospital(self, hospital_name: str) -> bool:
        if not hospital_name:
            return False
        hospitals: List[str] = self._data.get("network_hospitals", [])
        hospital_lower = hospital_name.lower()
        return any(h.lower() in hospital_lower or hospital_lower in h.lower() for h in hospitals)

    def get_network_hospitals(self) -> List[str]:
        return self._data.get("network_hospitals", [])

    def is_excluded_condition(self, diagnosis: str) -> bool:
        if not diagnosis:
            return False
        exclusions: List[str] = self._data.get("exclusions", {}).get("general", [])
        diag_lower = diagnosis.lower()
        return any(excl.lower() in diag_lower for excl in exclusions)

    def is_excluded_procedure(self, category: str, procedure: str) -> bool:
        if not procedure:
            return False
        cat_exclusions: List[str] = (
            self._data.get("exclusions", {}).get("category_specific", {}).get(category, [])
        )
        proc_lower = procedure.lower()
        return any(excl.lower() in proc_lower for excl in cat_exclusions)

    def get_exclusions(self) -> Dict[str, Any]:
        return self._data.get("exclusions", {})

    def get_fraud_thresholds(self) -> Dict[str, Any]:
        return self._data.get("fraud_thresholds", {})

    def get_submission_rules(self) -> Dict[str, Any]:
        return self._data.get("submission_rules", {})

    def get_pre_auth_rules(self) -> Dict[str, Any]:
        return self._data.get("pre_authorization", {})

    def get_annual_limit(self) -> float:
        return float(self._data.get("coverage", {}).get("annual_limit", 0))

    def get_per_claim_limit(self) -> float:
        return float(self._data.get("coverage", {}).get("per_claim_limit", 0))

    def get_minimum_claim_amount(self) -> float:
        return float(self._data.get("submission_rules", {}).get("minimum_claim_amount", 0))

    def get_submission_deadline_days(self) -> int:
        return int(self._data.get("submission_rules", {}).get("submission_deadline_days", 90))

    def get_all_categories(self) -> Dict[str, Any]:
        return self._data.get("opd_categories", {})

    def raw(self) -> Dict[str, Any]:
        return self._data
