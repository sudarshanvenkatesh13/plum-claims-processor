from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from models.claim import ClaimCategory, ClaimSubmission, ClaimResponse, UploadedDocument, PriorClaim
from orchestrator.pipeline import ClaimsPipeline
from services.policy_loader import PolicyLoader

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Plum Claims Processor",
    description="Multi-agent AI health insurance claims processing system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

claims_store: Dict[str, ClaimResponse] = {}
policy_loader: PolicyLoader = None  # type: ignore[assignment]
pipeline: ClaimsPipeline = None      # type: ignore[assignment]


@app.on_event("startup")
async def startup_event() -> None:
    global policy_loader, pipeline
    logger.info("Starting up Plum Claims Processor...")
    policy_loader = PolicyLoader(settings.POLICY_FILE_PATH)
    pipeline = ClaimsPipeline()
    logger.info("Startup complete. Policy loaded, pipeline ready.")


# ── Core claim endpoints ───────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "plum-claims-processor"}


@app.post("/api/claims/submit", response_model=ClaimResponse, tags=["Claims"])
async def submit_claim(submission: ClaimSubmission) -> ClaimResponse:
    logger.info(
        "Claim received | member=%s | category=%s | amount=%.2f",
        submission.member_id, submission.claim_category.value, submission.claimed_amount,
    )
    try:
        result = await pipeline.process(submission)
        claims_store[result.claim_id] = result
        logger.info("Claim %s processed | decision=%s", result.claim_id, result.decision)
        return result
    except Exception as exc:
        logger.exception("Unhandled error processing claim: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {exc}") from exc


@app.get("/api/claims/{claim_id}", response_model=ClaimResponse, tags=["Claims"])
async def get_claim(claim_id: str) -> ClaimResponse:
    if claim_id not in claims_store:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return claims_store[claim_id]


@app.get("/api/claims", tags=["Claims"])
async def list_claims() -> List[Dict[str, Any]]:
    return [
        {
            "claim_id": cid,
            "status": c.status,
            "decision": c.decision,
            "approved_amount": c.approved_amount,
            "confidence_score": c.confidence_score,
        }
        for cid, c in claims_store.items()
    ]


@app.get("/api/policy/members", tags=["Policy"])
async def get_members() -> List[Dict[str, Any]]:
    try:
        return [m.model_dump() for m in policy_loader.get_all_members()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/policy/categories", tags=["Policy"])
async def get_categories() -> Dict[str, Any]:
    try:
        result: Dict[str, Any] = {}
        for cat_name, cat_config in policy_loader.get_all_categories().items():
            result[cat_name] = {
                "config": cat_config,
                "document_requirements": policy_loader.get_document_requirements(cat_name),
            }
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Eval endpoint ─────────────────────────────────────────────────────────────

def _build_eval_submission(inp: Dict[str, Any]) -> ClaimSubmission:
    documents = []
    for d in inp.get("documents", []):
        content = d.get("content")
        patient_name_on_doc = d.get("patient_name_on_doc")
        if patient_name_on_doc and content is None:
            atype = (d.get("actual_type") or "").upper()
            if atype == "PRESCRIPTION":
                content = {"patient_name": patient_name_on_doc, "doctor_name": "Unknown Doctor"}
            elif atype == "HOSPITAL_BILL":
                content = {"patient_name": patient_name_on_doc, "hospital_name": "Unknown Hospital"}
            else:
                content = {"patient_name": patient_name_on_doc}
        documents.append(UploadedDocument(
            file_id=d["file_id"],
            file_name=d.get("file_name", f"{d['file_id']}.jpg"),
            file_content="",
            actual_type=d.get("actual_type"),
            quality=d.get("quality"),
            content=content,
        ))

    history = [
        PriorClaim(
            claim_id=c["claim_id"],
            date=date.fromisoformat(c["date"]),
            amount=float(c["amount"]),
            provider=c.get("provider", "Unknown"),
        )
        for c in inp.get("claims_history", [])
    ]

    return ClaimSubmission(
        member_id=inp["member_id"],
        policy_id=inp["policy_id"],
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=date.fromisoformat(inp["treatment_date"]),
        claimed_amount=float(inp["claimed_amount"]),
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=float(inp.get("ytd_claims_amount", 0)),
        simulate_component_failure=bool(inp.get("simulate_component_failure", False)),
        documents=documents,
        claims_history=history or None,
    )


def _eval_pass_fail(tc: Dict[str, Any], result: ClaimResponse) -> tuple[bool, str]:
    expected = tc["expected"]
    exp_decision = expected.get("decision")
    exp_amount = expected.get("approved_amount")

    failures: List[str] = []

    if exp_decision is None:
        if result.status != "stopped_early":
            failures.append(f"expected stopped_early, got {result.status}")
        if not result.error_message:
            failures.append("no error_message returned")
        case_id = tc["case_id"]
        if case_id == "TC003" and result.error_message:
            if "Rajesh Kumar" not in result.error_message or "Arjun Mehta" not in result.error_message:
                failures.append("TC003 error must name both patients")
        if case_id == "TC001" and result.error_message:
            msg = result.error_message.lower()
            if "hospital bill" not in msg and "hospital_bill" not in msg:
                failures.append("TC001 error must mention Hospital Bill")
        if case_id == "TC002" and result.error_message:
            if "unreadable" not in result.error_message.lower():
                failures.append("TC002 error must mention unreadable")
    else:
        if result.decision != exp_decision:
            failures.append(f"expected {exp_decision}, got {result.decision}")
        if exp_amount is not None:
            actual = result.approved_amount or 0.0
            if abs(actual - exp_amount) > 2.0:
                failures.append(f"expected ₹{exp_amount}, got ₹{actual:.0f}")
        if tc["case_id"] == "TC011":
            if result.confidence_score >= 0.95:
                failures.append(f"TC011 confidence too high: {result.confidence_score:.2f}")
            failure_noted = any(
                "component" in (r or "").lower() or "failure" in (r or "").lower()
                for r in (result.reasons or []) + (result.recommendations or []) + (result.errors or [])
            )
            if not failure_noted:
                failures.append("TC011 must note component failure")

    return (not failures), "; ".join(failures) if failures else "ok"


@app.post("/api/eval/run", tags=["Eval"])
async def run_eval() -> Dict[str, Any]:
    tc_path = Path(settings.POLICY_FILE_PATH).parent / "test_cases.json"
    if not tc_path.exists():
        raise HTTPException(status_code=404, detail="test_cases.json not found")

    with tc_path.open() as f:
        data = json.load(f)

    test_cases = data["test_cases"]
    results = []
    passed_count = 0

    for tc in test_cases:
        t0 = time.perf_counter()
        try:
            submission = _build_eval_submission(tc["input"])
            result = await pipeline.process(submission)
            passed, reason = _eval_pass_fail(tc, result)
        except Exception as exc:
            logger.exception("Eval error on %s: %s", tc["case_id"], exc)
            result = ClaimResponse(
                claim_id="ERROR",
                status="stopped_early",
                confidence_score=0.0,
                error_message=str(exc),
            )
            passed, reason = False, f"Exception: {exc}"

        duration_ms = round((time.perf_counter() - t0) * 1000)
        if passed:
            passed_count += 1

        expected = tc["expected"]
        results.append({
            "case_id": tc["case_id"],
            "case_name": tc["case_name"],
            "expected_decision": expected.get("decision"),
            "actual_decision": result.decision,
            "expected_amount": expected.get("approved_amount"),
            "actual_amount": result.approved_amount,
            "actual_status": result.status,
            "confidence_score": result.confidence_score,
            "passed": passed,
            "reason": reason,
            "error_message": result.error_message,
            "reasons": result.reasons[:3],
            "duration_ms": duration_ms,
        })

    return {
        "total": len(test_cases),
        "passed": passed_count,
        "failed": len(test_cases) - passed_count,
        "results": results,
    }


@app.get("/api/eval/test-cases", tags=["Eval"])
async def get_test_cases() -> Dict[str, Any]:
    tc_path = Path(settings.POLICY_FILE_PATH).parent / "test_cases.json"
    if not tc_path.exists():
        raise HTTPException(status_code=404, detail="test_cases.json not found")
    with tc_path.open() as f:
        return json.load(f)


class RunSingleRequest(BaseModel):
    case_id: str


@app.post("/api/eval/run-single", tags=["Eval"])
async def run_eval_single(req: RunSingleRequest) -> Dict[str, Any]:
    tc_path = Path(settings.POLICY_FILE_PATH).parent / "test_cases.json"
    if not tc_path.exists():
        raise HTTPException(status_code=404, detail="test_cases.json not found")

    with tc_path.open() as f:
        data = json.load(f)

    tc = next((t for t in data["test_cases"] if t["case_id"] == req.case_id), None)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{req.case_id}' not found")

    t0 = time.perf_counter()
    try:
        submission = _build_eval_submission(tc["input"])
        result = await pipeline.process(submission)
        passed, reason = _eval_pass_fail(tc, result)
    except Exception as exc:
        logger.exception("Eval error on %s: %s", req.case_id, exc)
        result = ClaimResponse(
            claim_id="ERROR",
            status="stopped_early",
            confidence_score=0.0,
            error_message=str(exc),
        )
        passed, reason = False, f"Exception: {exc}"

    duration_ms = round((time.perf_counter() - t0) * 1000)
    expected = tc["expected"]

    agent_timing: Dict[str, Any] = {}
    try:
        if result.trace and hasattr(result.trace, "entries"):
            for entry in result.trace.entries:
                if entry.duration_ms is not None:
                    agent_timing[entry.agent_name] = round(entry.duration_ms)
    except Exception:
        pass

    result_dict = result.model_dump(mode="json")
    result_dict.update({
        "case_id": tc["case_id"],
        "case_name": tc["case_name"],
        "expected_decision": expected.get("decision"),
        "expected_amount": expected.get("approved_amount"),
        "passed": passed,
        "reason": reason,
        "duration_ms": duration_ms,
        "agent_timing": agent_timing,
    })
    return result_dict
