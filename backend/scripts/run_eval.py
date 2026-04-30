"""
Evaluation harness for the 12 claims processing test cases.

Usage:
    cd backend
    python -m scripts.run_eval
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Ensure backend root is on sys.path ────────────────────────────────────────
_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))
os.environ.setdefault("OPENAI_API_KEY", "sk-eval-no-llm-needed")

from models.claim import ClaimCategory, ClaimSubmission, PriorClaim, UploadedDocument
from orchestrator.pipeline import ClaimsPipeline

# ── ANSI colour helpers ────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _green(s):  return f"{GREEN}{s}{RESET}"
def _red(s):    return f"{RED}{s}{RESET}"
def _yellow(s): return f"{YELLOW}{s}{RESET}"
def _cyan(s):   return f"{CYAN}{s}{RESET}"
def _bold(s):   return f"{BOLD}{s}{RESET}"


# ── Document builder ───────────────────────────────────────────────────────────

def _build_document(raw: Dict[str, Any]) -> UploadedDocument:
    """
    Map a test-case document dict to UploadedDocument.

    Handles two special fields:
    - patient_name_on_doc  → converted to content.patient_name (TC003)
    - test_name            → forwarded into content for lab reports (TC007)
    """
    content: Optional[Dict[str, Any]] = raw.get("content")

    # TC003: patient_name_on_doc shortcut — inject into content so extraction picks it up
    patient_name_on_doc = raw.get("patient_name_on_doc")
    if patient_name_on_doc and content is None:
        actual_type = (raw.get("actual_type") or "").upper()
        if actual_type == "PRESCRIPTION":
            content = {"patient_name": patient_name_on_doc, "doctor_name": "Unknown Doctor"}
        elif actual_type == "HOSPITAL_BILL":
            content = {"patient_name": patient_name_on_doc, "hospital_name": "Unknown Hospital"}
        else:
            content = {"patient_name": patient_name_on_doc}

    return UploadedDocument(
        file_id=raw["file_id"],
        file_name=raw.get("file_name", f"{raw['file_id']}.jpg"),
        file_content="",          # no real images in eval — all content is pre-populated
        actual_type=raw.get("actual_type"),
        quality=raw.get("quality"),
        content=content,
    )


# ── ClaimSubmission builder ────────────────────────────────────────────────────

def _build_submission(inp: Dict[str, Any]) -> ClaimSubmission:
    documents = [_build_document(d) for d in inp.get("documents", [])]

    claims_history: List[PriorClaim] = []
    for ch in inp.get("claims_history", []):
        claims_history.append(
            PriorClaim(
                claim_id=ch["claim_id"],
                date=date.fromisoformat(ch["date"]),
                amount=float(ch["amount"]),
                provider=ch.get("provider", "Unknown"),
            )
        )

    return ClaimSubmission(
        member_id=inp["member_id"],
        policy_id=inp["policy_id"],
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=date.fromisoformat(inp["treatment_date"]),
        # submission_date left as None → pipeline defaults to treatment_date (always within deadline)
        claimed_amount=float(inp["claimed_amount"]),
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=float(inp.get("ytd_claims_amount", 0)),
        simulate_component_failure=bool(inp.get("simulate_component_failure", False)),
        documents=documents,
        claims_history=claims_history or None,
    )


# ── Pass / fail evaluator ──────────────────────────────────────────────────────

def _evaluate(tc: Dict[str, Any], result) -> Tuple[bool, str]:
    """
    Returns (passed: bool, reason: str).

    TC001–TC003: expected decision is null — check stopped_early + error_message quality.
    TC004–TC012: check decision and (where given) approved_amount.
    """
    expected      = tc["expected"]
    exp_decision  = expected.get("decision")       # None means "stopped early"
    exp_amount    = expected.get("approved_amount")
    exp_confidence= expected.get("confidence_score")  # e.g. "above 0.85"
    system_musts  = expected.get("system_must", [])

    failures: List[str] = []

    # ── Cases where pipeline must stop early (null decision) ──────────────────
    if exp_decision is None:
        if result.status != "stopped_early":
            failures.append(f"expected status=stopped_early, got {result.status!r}")
        if not result.error_message:
            failures.append("expected a specific error_message but got none")

        # TC003 specific: both patient names must appear in the error message
        case_id = tc["case_id"]
        if case_id == "TC003" and result.error_message:
            msg = result.error_message
            if "Rajesh Kumar" not in msg or "Arjun Mehta" not in msg:
                failures.append(
                    f"TC003 error_message must name both patients; got: {msg!r}"
                )
        # TC001: error must reference missing document type
        if case_id == "TC001" and result.error_message:
            msg = result.error_message.lower()
            if "hospital bill" not in msg and "hospital_bill" not in msg:
                failures.append(
                    f"TC001 error_message must mention 'Hospital Bill'; got: {result.error_message!r}"
                )
        # TC002: error must mention unreadable
        if case_id == "TC002" and result.error_message:
            if "unreadable" not in result.error_message.lower():
                failures.append(
                    f"TC002 error_message must mention 'unreadable'; got: {result.error_message!r}"
                )

        return (not failures), "; ".join(failures) if failures else "stopped_early with specific error ✓"

    # ── Cases with an expected decision ──────────────────────────────────────
    if result.decision != exp_decision:
        failures.append(f"expected decision={exp_decision!r}, got {result.decision!r}")

    # Amount check (allow ±₹2 rounding)
    if exp_amount is not None:
        actual_amount = result.approved_amount or 0.0
        if abs(actual_amount - exp_amount) > 2.0:
            failures.append(
                f"expected approved_amount=₹{exp_amount:,}, got ₹{actual_amount:,.2f}"
            )

    # Confidence threshold check
    if exp_confidence and isinstance(exp_confidence, str) and exp_confidence.startswith("above "):
        threshold = float(exp_confidence.split()[-1])
        if result.confidence_score < threshold:
            failures.append(
                f"expected confidence {exp_confidence}, got {result.confidence_score:.2f}"
            )

    # TC011: must NOT be a crash, must note component failure, confidence < 1.0
    if tc["case_id"] == "TC011":
        if result.status == "stopped_early" and not result.decision:
            failures.append("TC011 must produce a decision (pipeline must not abort on component failure)")
        low_confidence = result.confidence_score < 0.95
        failure_noted = any(
            "component" in (r or "").lower() or "failure" in (r or "").lower()
            for r in (result.reasons or []) + (result.recommendations or []) + (result.errors or [])
        )
        if not low_confidence:
            failures.append(f"TC011 confidence should be reduced, got {result.confidence_score:.2f}")
        if not failure_noted:
            failures.append("TC011 output must note the component failure")

    return (not failures), "; ".join(failures) if failures else "✓"


# ── Pretty printer ─────────────────────────────────────────────────────────────

def _print_result(tc: Dict[str, Any], result, passed: bool, reason: str) -> None:
    case_id   = tc["case_id"]
    case_name = tc["case_name"]
    expected  = tc["expected"]
    exp_dec   = expected.get("decision", "STOP")
    exp_amt   = expected.get("approved_amount")

    status_str = _green("PASS") if passed else _red("FAIL")
    dec_str    = result.decision or "(none)"
    amt_str    = f"₹{result.approved_amount:,.0f}" if result.approved_amount else "—"
    conf_str   = f"{result.confidence_score:.0%}"

    print(f"\n{'─'*72}")
    print(f"  {_bold(case_id)} · {case_name}")
    print(f"  Status:   {result.status}")
    print(f"  Decision: {_cyan(dec_str):30s}  Expected: {_cyan(str(exp_dec))}")
    print(f"  Amount:   {amt_str:20s}  Expected: {f'₹{exp_amt:,}' if exp_amt else '—'}")
    print(f"  Confidence: {conf_str}")

    if result.error_message:
        print(f"  Error msg: {_yellow(result.error_message)}")

    if result.reasons:
        for r in result.reasons[:3]:  # cap at 3 lines
            print(f"    · {r}")
        if len(result.reasons) > 3:
            print(f"    · … ({len(result.reasons)-3} more)")

    if result.recommendations:
        for rec in result.recommendations[:2]:
            print(f"    ► {rec}")

    print(f"\n  {status_str}  {reason if not passed else ''}")


# ── Main runner ────────────────────────────────────────────────────────────────

async def run_all(test_cases_path: str) -> None:
    data_path = Path(test_cases_path)
    if not data_path.exists():
        print(_red(f"test_cases.json not found at {data_path}"))
        sys.exit(1)

    with data_path.open() as f:
        data = json.load(f)

    test_cases: List[Dict[str, Any]] = data["test_cases"]

    print(_bold(f"\n{'='*72}"))
    print(_bold(f"  Plum Claims Processor — Evaluation Suite ({len(test_cases)} cases)"))
    print(_bold(f"{'='*72}"))

    pipeline = ClaimsPipeline()

    passed_count = 0
    failed_count = 0
    results_summary: List[Tuple[str, str, bool, str]] = []

    for tc in test_cases:
        case_id   = tc["case_id"]
        case_name = tc["case_name"]
        print(f"\nRunning {_bold(case_id)} — {case_name} …", end=" ", flush=True)

        try:
            submission = _build_submission(tc["input"])
            result     = await pipeline.process(submission)
            passed, reason = _evaluate(tc, result)
        except Exception as exc:
            print(_red(f"EXCEPTION: {exc}"))
            import traceback
            traceback.print_exc()
            result  = type("R", (), {
                "status": "exception", "decision": None, "approved_amount": None,
                "confidence_score": 0.0, "error_message": str(exc),
                "reasons": [], "recommendations": [], "errors": [],
            })()
            passed, reason = False, f"Unhandled exception: {exc}"

        if passed:
            passed_count += 1
            print(_green("✓"))
        else:
            failed_count += 1
            print(_red("✗"))

        _print_result(tc, result, passed, reason)
        results_summary.append((case_id, case_name, passed, reason))

    # ── Summary table ──────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(_bold("  SUMMARY"))
    print(f"{'─'*72}")
    for case_id, case_name, passed, reason in results_summary:
        icon  = _green("✓ PASS") if passed else _red("✗ FAIL")
        extra = f"  ← {reason}" if not passed else ""
        print(f"  {icon}  {case_id:<8} {case_name}{extra}")

    total = passed_count + failed_count
    print(f"{'─'*72}")
    colour = GREEN if failed_count == 0 else RED
    print(f"  {colour}{BOLD}Total: {passed_count}/{total} passed  ({failed_count} failed){RESET}")
    print(f"{'='*72}\n")


def main() -> None:
    test_cases_path = str(_BACKEND_DIR / "data" / "test_cases.json")
    asyncio.run(run_all(test_cases_path))


if __name__ == "__main__":
    main()
