"""Agent 1: Verifies that the correct document types were uploaded for the claim category."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from models.document import ClassifiedDocument, DocVerificationResult, DocumentQuality, DocumentType

logger = logging.getLogger(__name__)

# Human-readable display names for DocumentType values
_DOC_TYPE_LABELS: Dict[str, str] = {
    "PRESCRIPTION": "Prescription",
    "HOSPITAL_BILL": "Hospital Bill",
    "LAB_REPORT": "Lab Report",
    "PHARMACY_BILL": "Pharmacy Bill",
    "DENTAL_REPORT": "Dental Report",
    "DIAGNOSTIC_REPORT": "Diagnostic Report",
    "DISCHARGE_SUMMARY": "Discharge Summary",
    "UNKNOWN": "Unknown Document",
}


def _label(doc_type: str) -> str:
    return _DOC_TYPE_LABELS.get(doc_type, doc_type)


async def run_document_verification(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 1 (DocumentVerification): starting")

    documents = state.get("documents", [])
    category: str = state.get("claim_category", "")
    policy_loader = state.get("policy_loader")

    # --- 1. No documents at all ---
    if not documents:
        result = DocVerificationResult(
            status="failed",
            missing_documents=["No documents uploaded"],
            error_message="No documents were submitted with this claim. Please upload the required documents.",
        )
        logger.warning("Agent 1: no documents uploaded")
        return {**state, "doc_verification_result": result, "pipeline_stop": True}

    # --- 2. Classify each document ---
    classified: List[ClassifiedDocument] = []
    quality_issues: List[str] = []

    for doc in documents:
        # Use pre-set actual_type when available (test cases / trusted uploads)
        if doc.actual_type:
            try:
                detected_type = DocumentType(doc.actual_type.upper())
            except ValueError:
                detected_type = DocumentType.UNKNOWN

            quality_str = (doc.quality or "GOOD").upper()
            try:
                quality = DocumentQuality(quality_str)
            except ValueError:
                quality = DocumentQuality.GOOD

            confidence = 1.0
        else:
            # Call LLM to classify the document from base64 image
            llm = state.get("llm_service")
            if llm and doc.file_content:
                classify_result = await llm.classify_document(doc.file_content)
                detected_type = classify_result.get("document_type", DocumentType.UNKNOWN)
                quality = classify_result.get("quality", DocumentQuality.POOR)
                confidence = classify_result.get("confidence", 0.5)
            else:
                detected_type = DocumentType.UNKNOWN
                quality = DocumentQuality.POOR
                confidence = 0.0

        classified.append(
            ClassifiedDocument(
                file_id=doc.file_id,
                file_name=doc.file_name,
                detected_type=detected_type,
                quality=quality,
                confidence=confidence,
            )
        )

        # --- 3. Unreadable quality check (TC002) ---
        if quality == DocumentQuality.UNREADABLE:
            quality_issues.append(doc.file_name)

    # Fail immediately on any unreadable document
    if quality_issues:
        names = ", ".join(f"'{n}'" for n in quality_issues)
        plural = "are" if len(quality_issues) > 1 else "is"
        result = DocVerificationResult(
            status="failed",
            classified_documents=classified,
            quality_issues=quality_issues,
            error_message=(
                f"The following document(s) {plural} unreadable: {names}. "
                f"Please re-upload a clear, legible copy of "
                f"{'these documents' if len(quality_issues) > 1 else 'this document'} "
                f"and resubmit your claim."
            ),
        )
        logger.warning("Agent 1: unreadable documents: %s", quality_issues)
        return {**state, "doc_verification_result": result, "pipeline_stop": True}

    # --- 4. Check required document types ---
    if policy_loader:
        reqs = policy_loader.get_document_requirements(category)
    else:
        reqs = {"required": [], "optional": []}

    required_types: List[str] = reqs.get("required", [])

    # Build a counter of detected types (ignoring UNKNOWN for coverage check)
    detected_counts: Counter = Counter(
        c.detected_type.value for c in classified if c.detected_type != DocumentType.UNKNOWN
    )

    # Find missing required types
    missing: List[str] = [rt for rt in required_types if detected_counts.get(rt, 0) == 0]

    if missing:
        # Build a specific, actionable error message (TC001)
        uploaded_summary = _build_uploaded_summary(detected_counts)
        missing_summary = " and ".join(_label(m) for m in missing)
        required_summary = ", ".join(_label(r) for r in required_types)

        error_msg = (
            f"You uploaded {uploaded_summary} but no {missing_summary}. "
            f"A {_label_category(category)} claim requires: {required_summary}. "
            f"Please upload your {missing_summary} and resubmit."
        )
        result = DocVerificationResult(
            status="failed",
            classified_documents=classified,
            missing_documents=missing,
            error_message=error_msg,
        )
        logger.warning("Agent 1: missing required docs for %s: %s", category, missing)
        return {**state, "doc_verification_result": result, "pipeline_stop": True}

    # All checks passed
    result = DocVerificationResult(
        status="passed",
        classified_documents=classified,
    )
    logger.info("Agent 1: verification passed — %d documents classified", len(classified))
    return {**state, "doc_verification_result": result}


def _build_uploaded_summary(detected_counts: Counter) -> str:
    """Build a human-readable summary of what was uploaded, e.g. '2 Prescriptions and 1 Lab Report'."""
    if not detected_counts:
        return "no recognisable documents"
    parts = []
    for doc_type, count in detected_counts.items():
        label = _label(doc_type)
        # Naive pluralisation
        if count > 1:
            label = f"{count} {label}s"
        parts.append(label)
    return " and ".join(parts)


def _label_category(category: str) -> str:
    return category.replace("_", " ").title()
