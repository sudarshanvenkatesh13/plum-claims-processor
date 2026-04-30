"""Agent 3: Cross-validates consistency across all extracted documents."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.decision import CrossValidationResult
from models.document import (
    BillExtraction,
    DentalReportExtraction,
    DiagnosticReportExtraction,
    DischargeSummaryExtraction,
    DocumentExtractionResult,
    DocumentType,
    LabReportExtraction,
    PharmacyBillExtraction,
    PrescriptionExtraction,
)

logger = logging.getLogger(__name__)


def _normalise(name: Optional[str]) -> str:
    """Lowercase, strip, collapse whitespace for comparison."""
    if not name:
        return ""
    return " ".join(name.lower().split())


def _names_match(a: str, b: str) -> bool:
    """Case-insensitive name match, allowing minor variations."""
    na, nb = _normalise(a), _normalise(b)
    if not na or not nb:
        return True  # treat missing names as non-contradictory
    if na == nb:
        return True
    # Allow if one name contains the other (e.g. "Rajesh Kumar" vs "Mr Rajesh Kumar")
    if na in nb or nb in na:
        return True
    return False


def _extract_patient_name(er: DocumentExtractionResult) -> Optional[str]:
    if not er.extraction:
        return None
    ext = er.extraction
    if isinstance(ext, PrescriptionExtraction):
        return ext.patient_name
    if isinstance(ext, BillExtraction):
        return ext.patient_name
    if isinstance(ext, LabReportExtraction):
        return ext.patient_name
    if isinstance(ext, PharmacyBillExtraction):
        return ext.patient_name
    if isinstance(ext, DentalReportExtraction):
        return ext.patient_name
    if isinstance(ext, DiagnosticReportExtraction):
        return ext.patient_name
    if isinstance(ext, DischargeSummaryExtraction):
        return ext.patient_name
    return None


def _extract_date(er: DocumentExtractionResult) -> Optional[str]:
    if not er.extraction:
        return None
    ext = er.extraction
    for attr in ("date", "admission_date"):
        val = getattr(ext, attr, None)
        if val:
            return str(val)
    return None


def _extract_amount(er: DocumentExtractionResult) -> Optional[float]:
    if not er.extraction:
        return None
    ext = er.extraction
    for attr in ("total", "net_amount", "total_bill"):
        val = getattr(ext, attr, None)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _doc_label(doc_type: DocumentType) -> str:
    return doc_type.value.replace("_", " ").title()


async def run_cross_validation(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 3 (CrossValidation): starting")

    extraction_results: List[DocumentExtractionResult] = state.get("extraction_results", [])
    claimed_amount: float = state.get("claimed_amount", 0.0)
    member_id: str = state.get("member_id", "")
    policy_loader = state.get("policy_loader")
    mismatches: List[Dict[str, Any]] = []

    # Skip if nothing was extracted (e.g. component failure with no data)
    if not extraction_results:
        result = CrossValidationResult(status="passed")
        return {**state, "cross_validation_result": result}

    # ------------------------------------------------------------------
    # 1. Collect patient names per document
    # ------------------------------------------------------------------
    named_docs: List[Tuple[str, str]] = []  # (doc_label, patient_name)
    for er in extraction_results:
        name = _extract_patient_name(er)
        if name:
            named_docs.append((_doc_label(er.document_type), name))

    # ------------------------------------------------------------------
    # 2. Check patient name consistency across documents (TC003)
    # ------------------------------------------------------------------
    patient_name_match = True
    if len(named_docs) >= 2:
        reference_label, reference_name = named_docs[0]
        for doc_label, name in named_docs[1:]:
            if not _names_match(reference_name, name):
                patient_name_match = False
                mismatches.append(
                    {
                        "type": "patient_name_mismatch",
                        "doc_a": reference_label,
                        "name_a": reference_name,
                        "doc_b": doc_label,
                        "name_b": name,
                    }
                )

    if not patient_name_match:
        # Build a specific, actionable error (TC003)
        mismatch = mismatches[0]
        error_msg = (
            f"Patient name mismatch across documents: "
            f"the {mismatch['doc_a']} is issued to '{mismatch['name_a']}' "
            f"but the {mismatch['doc_b']} is for '{mismatch['name_b']}'. "
            f"Please ensure all documents belong to the same patient and resubmit."
        )
        result = CrossValidationResult(
            status="failed",
            patient_name_match=False,
            mismatches=mismatches,
            error_message=error_msg,
        )
        logger.warning("Agent 3: name mismatch — %s", error_msg)
        return {**state, "cross_validation_result": result, "pipeline_stop": True}

    # ------------------------------------------------------------------
    # 3. Check member name matches any document patient name (advisory)
    # ------------------------------------------------------------------
    member_name_match = True
    if policy_loader and named_docs:
        member = policy_loader.get_member(member_id)
        if member:
            doc_names = [n for _, n in named_docs]
            member_name_match = any(_names_match(member.name, dn) for dn in doc_names)
            if not member_name_match:
                mismatches.append(
                    {
                        "type": "member_name_mismatch",
                        "member_name": member.name,
                        "document_names": doc_names,
                    }
                )
                logger.warning(
                    "Agent 3: member name '%s' does not match document patient names %s — advisory",
                    member.name,
                    doc_names,
                )

    # ------------------------------------------------------------------
    # 4. Date consistency (advisory — dates may not always be present)
    # ------------------------------------------------------------------
    date_match = True
    dated_docs = [(er.document_type.value, _extract_date(er)) for er in extraction_results]
    dated_only = [(dt, d) for dt, d in dated_docs if d]
    if len(dated_only) >= 2:
        ref_date = dated_only[0][1]
        for dt, d in dated_only[1:]:
            if d != ref_date:
                date_match = False
                mismatches.append({"type": "date_mismatch", "doc": dt, "date": d, "expected": ref_date})
                break

    # ------------------------------------------------------------------
    # 5. Amount consistency (advisory)
    # ------------------------------------------------------------------
    amount_match = True
    bill_amounts = [
        _extract_amount(er)
        for er in extraction_results
        if er.document_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL)
        and _extract_amount(er) is not None
    ]
    if bill_amounts:
        bill_total = sum(bill_amounts)
        # Allow 5% variance between claimed amount and billed total
        if abs(bill_total - claimed_amount) / max(claimed_amount, 1) > 0.05:
            amount_match = False
            mismatches.append(
                {
                    "type": "amount_mismatch",
                    "billed_total": bill_total,
                    "claimed_amount": claimed_amount,
                }
            )
            logger.info("Agent 3: amount advisory — billed %.2f vs claimed %.2f", bill_total, claimed_amount)

    result = CrossValidationResult(
        status="passed",
        patient_name_match=patient_name_match,
        date_match=date_match,
        amount_match=amount_match,
        member_name_match=member_name_match,
        mismatches=mismatches,
    )
    logger.info("Agent 3: passed — %d advisory mismatches noted", len(mismatches))
    return {**state, "cross_validation_result": result}
