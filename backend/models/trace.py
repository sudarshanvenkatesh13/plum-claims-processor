from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceEntry(BaseModel):
    agent_name: str
    status: str  # "success" | "failed" | "skipped"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    # Structured per-agent summary for the frontend trace viewer
    summary: Dict[str, Any] = Field(default_factory=dict)


class DecisionTrace(BaseModel):
    entries: List[TraceEntry] = Field(default_factory=list)
    total_duration_ms: Optional[float] = None
    pipeline_status: str = "pending"  # "pending" | "completed" | "stopped_early" | "failed"
