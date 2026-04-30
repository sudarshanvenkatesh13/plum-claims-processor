from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemberInfo(BaseModel):
    member_id: str
    name: str
    age: int
    gender: Optional[str] = None
    relationship: Optional[str] = None
    policy_id: Optional[str] = None
    pre_existing_conditions: List[str] = Field(default_factory=list)


class CoverageInfo(BaseModel):
    annual_limit: float
    per_claim_limit: Optional[float] = None
    copay_percentage: float = 0.0
    network_discount: float = 0.0
    sub_limits: Dict[str, float] = Field(default_factory=dict)
    exclusions: List[str] = Field(default_factory=list)
    waiting_period_days: int = 0


class PolicyTerms(BaseModel):
    policy_id: str
    policy_name: str
    insurer: Optional[str] = None
    members: List[MemberInfo] = Field(default_factory=list)
    coverage: Optional[CoverageInfo] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
