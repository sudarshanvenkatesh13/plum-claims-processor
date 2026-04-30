"""LangGraph state machine orchestrating all 6 claim-processing agents."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from agents import (
    run_document_verification,
    run_document_extraction,
    run_cross_validation,
    run_policy_evaluation,
    run_fraud_detection,
    run_decision_aggregation,
)
from models.claim import ClaimSubmission, ClaimResponse
from models.decision import Decision
from models.trace import DecisionTrace, TraceEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangGraph state type — a plain dict so we can add keys at each node
# ---------------------------------------------------------------------------
ClaimState = Dict[str, Any]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ms(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() * 1000


async def _timed_node(name: str, fn, state: ClaimState) -> ClaimState:
    """Wraps an agent function with timing and trace recording."""
    started = _now()
    trace_entries: List[TraceEntry] = state.get("_trace_entries", [])
    try:
        new_state = await fn(state)
        completed = _now()
        entry = TraceEntry(
            agent_name=name,
            status="success",
            started_at=started,
            completed_at=completed,
            duration_ms=_ms(started, completed),
            details={k: str(v)[:200] for k, v in new_state.items() if not k.startswith("_") and k != "documents"},
        )
    except Exception as exc:
        completed = _now()
        logger.exception("Agent %s raised an exception: %s", name, exc)
        entry = TraceEntry(
            agent_name=name,
            status="failed",
            started_at=started,
            completed_at=completed,
            duration_ms=_ms(started, completed),
            errors=[str(exc)],
        )
        new_state = {**state, "pipeline_stop": True, "_agent_error": str(exc)}

    trace_entries = trace_entries + [entry]
    return {**new_state, "_trace_entries": trace_entries}


# ---------------------------------------------------------------------------
# Node wrappers
# ---------------------------------------------------------------------------

async def node_doc_verification(state: ClaimState) -> ClaimState:
    return await _timed_node("DocumentVerification", run_document_verification, state)


async def node_doc_extraction(state: ClaimState) -> ClaimState:
    return await _timed_node("DocumentExtraction", run_document_extraction, state)


async def node_cross_validation(state: ClaimState) -> ClaimState:
    return await _timed_node("CrossValidation", run_cross_validation, state)


async def node_policy_evaluation(state: ClaimState) -> ClaimState:
    return await _timed_node("PolicyEvaluation", run_policy_evaluation, state)


async def node_fraud_detection(state: ClaimState) -> ClaimState:
    return await _timed_node("FraudDetection", run_fraud_detection, state)


async def node_decision_aggregation(state: ClaimState) -> ClaimState:
    return await _timed_node("DecisionAggregation", run_decision_aggregation, state)


# ---------------------------------------------------------------------------
# Conditional edge: stop early if pipeline_stop is set
# ---------------------------------------------------------------------------

def should_continue(state: ClaimState) -> str:
    if state.get("pipeline_stop"):
        return "stop"
    return "continue"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph() -> Any:
    graph = StateGraph(ClaimState)

    graph.add_node("doc_verification", node_doc_verification)
    graph.add_node("doc_extraction", node_doc_extraction)
    graph.add_node("cross_validation", node_cross_validation)
    graph.add_node("policy_evaluation", node_policy_evaluation)
    graph.add_node("fraud_detection", node_fraud_detection)
    graph.add_node("decision_aggregation", node_decision_aggregation)

    graph.set_entry_point("doc_verification")

    # After verification, check if we should stop (e.g. no docs uploaded)
    graph.add_conditional_edges(
        "doc_verification",
        should_continue,
        {"continue": "doc_extraction", "stop": "decision_aggregation"},
    )
    graph.add_conditional_edges(
        "doc_extraction",
        should_continue,
        {"continue": "cross_validation", "stop": "decision_aggregation"},
    )
    graph.add_conditional_edges(
        "cross_validation",
        should_continue,
        {"continue": "policy_evaluation", "stop": "decision_aggregation"},
    )
    graph.add_conditional_edges(
        "policy_evaluation",
        should_continue,
        {"continue": "fraud_detection", "stop": "decision_aggregation"},
    )
    graph.add_edge("fraud_detection", "decision_aggregation")
    graph.add_edge("decision_aggregation", END)

    return graph.compile()


_COMPILED_GRAPH = None


def get_graph() -> Any:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = _build_graph()
    return _COMPILED_GRAPH


# ---------------------------------------------------------------------------
# Public pipeline class
# ---------------------------------------------------------------------------

class ClaimsPipeline:
    def __init__(self) -> None:
        self._graph = get_graph()

    async def process(self, submission: ClaimSubmission) -> ClaimResponse:
        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        pipeline_start = _now()

        # Flatten submission into initial state dict
        initial_state: ClaimState = {
            "claim_id": claim_id,
            "member_id": submission.member_id,
            "policy_id": submission.policy_id,
            "claim_category": submission.claim_category.value,
            "treatment_date": submission.treatment_date,
            "claimed_amount": submission.claimed_amount,
            "hospital_name": submission.hospital_name,
            "documents": submission.documents,
            "claims_history": submission.claims_history or [],
            "ytd_claims_amount": submission.ytd_claims_amount or 0.0,
            "simulate_component_failure": submission.simulate_component_failure,
            "pipeline_stop": False,
            "_trace_entries": [],
        }

        try:
            final_state: ClaimState = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.exception("Pipeline invocation failed for claim %s: %s", claim_id, exc)
            final_state = {**initial_state, "pipeline_stop": True, "_agent_error": str(exc)}

        pipeline_end = _now()

        # Build trace
        trace_entries: List[TraceEntry] = final_state.get("_trace_entries", [])
        pipeline_stopped = final_state.get("pipeline_stop", False)
        trace = DecisionTrace(
            entries=trace_entries,
            total_duration_ms=_ms(pipeline_start, pipeline_end),
            pipeline_status="stopped_early" if pipeline_stopped else "completed",
        )

        # Resolve final decision
        final_decision = final_state.get("final_decision")
        decision_value: Optional[str] = None
        approved_amount: Optional[float] = None
        confidence: float = 0.0
        reasons: List[str] = []
        recommendations: List[str] = []
        errors: List[str] = []

        if final_decision:
            decision_value = final_decision.decision.value
            approved_amount = final_decision.approved_amount
            confidence = final_decision.confidence_score
            reasons = final_decision.reasons
            recommendations = final_decision.recommendations
            errors = final_decision.errors

        if final_state.get("_agent_error"):
            errors.append(final_state["_agent_error"])

        doc_error: Optional[str] = None
        doc_result = final_state.get("doc_verification_result")
        if doc_result and doc_result.status == "failed":
            doc_error = doc_result.error_message

        status = "stopped_early" if pipeline_stopped else "completed"

        return ClaimResponse(
            claim_id=claim_id,
            status=status,
            decision=decision_value,
            approved_amount=approved_amount,
            confidence_score=confidence,
            reasons=reasons,
            trace=trace,
            errors=errors,
            recommendations=recommendations,
            error_message=doc_error,
        )
