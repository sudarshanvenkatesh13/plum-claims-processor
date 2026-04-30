"""Agent 2: Extracts structured data from each document via GPT-4o Vision."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models.document import (
    BillExtraction,
    ClassifiedDocument,
    DentalReportExtraction,
    DiagnosticReportExtraction,
    DischargeSummaryExtraction,
    DocumentExtractionResult,
    DocumentType,
    LabReportExtraction,
    LabTest,
    LineItem,
    PharmacyBillExtraction,
    PharmacyMedicine,
    PrescriptionExtraction,
)

logger = logging.getLogger(__name__)


def _map_content_to_extraction(doc_type: DocumentType, content: Dict[str, Any]):
    """Convert pre-populated test-case content dict to the appropriate extraction model."""
    try:
        if doc_type == DocumentType.PRESCRIPTION:
            return PrescriptionExtraction(
                doctor_name=content.get("doctor_name"),
                doctor_registration=content.get("doctor_registration"),
                patient_name=content.get("patient_name"),
                age=str(content["age"]) if content.get("age") else None,
                gender=content.get("gender"),
                date=content.get("date"),
                diagnosis=content.get("diagnosis"),
                hospital_name=content.get("hospital_name"),
                medicines=content.get("medicines", []),
                tests_ordered=content.get("tests_ordered", []),
            )
        elif doc_type == DocumentType.HOSPITAL_BILL:
            raw_items = content.get("line_items", [])
            line_items = [
                LineItem(description=i.get("description", ""), amount=float(i.get("amount", 0)))
                for i in raw_items
                if isinstance(i, dict)
            ]
            return BillExtraction(
                hospital_name=content.get("hospital_name"),
                patient_name=content.get("patient_name"),
                date=content.get("date"),
                line_items=line_items,
                total=float(content["total"]) if content.get("total") is not None else None,
                gstin=content.get("gstin"),
            )
        elif doc_type == DocumentType.LAB_REPORT:
            raw_tests = content.get("tests", [])
            # Handle single-test shortcut: {"test_name": "MRI Lumbar Spine"}
            if not raw_tests and content.get("test_name"):
                raw_tests = [{"name": content["test_name"]}]
            tests = [
                LabTest(
                    name=t.get("name", ""),
                    result=t.get("result"),
                    unit=t.get("unit"),
                    normal_range=t.get("normal_range"),
                )
                for t in raw_tests
                if isinstance(t, dict)
            ]
            return LabReportExtraction(
                lab_name=content.get("lab_name"),
                patient_name=content.get("patient_name"),
                doctor_name=content.get("doctor_name"),
                date=content.get("date"),
                tests=tests,
                remarks=content.get("remarks"),
            )
        elif doc_type == DocumentType.PHARMACY_BILL:
            raw_meds = content.get("medicines", [])
            meds = [
                PharmacyMedicine(
                    name=m.get("name", ""),
                    qty=str(m["qty"]) if m.get("qty") else None,
                    amount=float(m["amount"]) if m.get("amount") is not None else None,
                )
                for m in raw_meds
                if isinstance(m, dict)
            ]
            return PharmacyBillExtraction(
                pharmacy_name=content.get("pharmacy_name"),
                patient_name=content.get("patient_name"),
                date=content.get("date"),
                medicines=meds,
                total=float(content["total"]) if content.get("total") is not None else None,
                discount=float(content["discount"]) if content.get("discount") is not None else None,
                net_amount=float(content["net_amount"]) if content.get("net_amount") is not None else None,
            )
        elif doc_type == DocumentType.DENTAL_REPORT:
            return DentalReportExtraction(
                dentist_name=content.get("dentist_name"),
                patient_name=content.get("patient_name"),
                date=content.get("date"),
                procedure=content.get("procedure"),
                tooth_numbers=content.get("tooth_numbers", []),
                materials_used=content.get("materials_used", []),
                total=float(content["total"]) if content.get("total") is not None else None,
            )
        elif doc_type == DocumentType.DIAGNOSTIC_REPORT:
            return DiagnosticReportExtraction(
                center_name=content.get("center_name"),
                patient_name=content.get("patient_name"),
                doctor_name=content.get("doctor_name"),
                date=content.get("date"),
                modality=content.get("modality"),
                body_part=content.get("body_part"),
                findings=content.get("findings"),
                impression=content.get("impression"),
            )
        elif doc_type == DocumentType.DISCHARGE_SUMMARY:
            return DischargeSummaryExtraction(
                hospital_name=content.get("hospital_name"),
                patient_name=content.get("patient_name"),
                admission_date=content.get("admission_date"),
                discharge_date=content.get("discharge_date"),
                diagnosis=content.get("diagnosis"),
                procedures=content.get("procedures", []),
                discharge_condition=content.get("discharge_condition"),
                follow_up=content.get("follow_up"),
                total_bill=float(content["total_bill"]) if content.get("total_bill") is not None else None,
            )
    except Exception as exc:
        logger.warning("Content mapping failed for %s: %s", doc_type, exc)
    return None


async def run_document_extraction(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Agent 2 (DocumentExtraction): starting")

    doc_verification_result = state.get("doc_verification_result")
    documents = state.get("documents", [])
    llm = state.get("llm_service")
    simulate_failure: bool = state.get("simulate_component_failure", False)

    # Build a lookup: file_id → ClassifiedDocument (from Agent 1)
    classified_map: Dict[str, ClassifiedDocument] = {}
    if doc_verification_result:
        for cd in doc_verification_result.classified_documents:
            classified_map[cd.file_id] = cd

    extraction_results: List[DocumentExtractionResult] = []
    component_failed = False

    for idx, doc in enumerate(documents):
        classified = classified_map.get(doc.file_id)
        doc_type = classified.detected_type if classified else DocumentType.UNKNOWN

        # TC011: simulate component failure on the first document
        if simulate_failure and idx == 0:
            logger.warning("Agent 2: simulating component failure for doc %s", doc.file_id)
            extraction_results.append(
                DocumentExtractionResult(
                    file_id=doc.file_id,
                    document_type=doc_type,
                    confidence=0.0,
                    error="Simulated component failure during extraction",
                )
            )
            component_failed = True
            continue  # pipeline CONTINUES — do not set pipeline_stop

        try:
            extraction, confidence, field_confidences, raw_text, error = await _extract_single(
                doc, doc_type, llm
            )
            extraction_results.append(
                DocumentExtractionResult(
                    file_id=doc.file_id,
                    document_type=doc_type,
                    extraction=extraction,
                    confidence=confidence,
                    raw_text=raw_text,
                    field_confidences=field_confidences,
                    error=error,
                )
            )
        except Exception as exc:
            logger.exception("Agent 2: unhandled error extracting %s: %s", doc.file_id, exc)
            extraction_results.append(
                DocumentExtractionResult(
                    file_id=doc.file_id,
                    document_type=doc_type,
                    confidence=0.0,
                    error=str(exc),
                )
            )
            component_failed = True

    new_state: Dict[str, Any] = {**state, "extraction_results": extraction_results}
    if component_failed:
        new_state["_component_failed"] = True

    logger.info(
        "Agent 2: extracted %d documents, component_failed=%s", len(extraction_results), component_failed
    )
    return new_state


async def _extract_single(doc, doc_type: DocumentType, llm):
    """Returns (extraction, confidence, field_confidences, raw_text, error)."""
    # Pre-populated content from test case data
    if doc.content:
        extraction = _map_content_to_extraction(doc_type, doc.content)
        if extraction:
            field_confidences = {
                field: 1.0
                for field in extraction.model_fields
                if getattr(extraction, field, None) is not None
            }
            return extraction, 1.0, field_confidences, None, None
        return None, 0.0, {}, None, "Failed to map pre-populated content"

    # LLM extraction from image
    if llm and doc.file_content:
        result = await llm.extract_document(doc.file_content, doc_type)
        return (
            result.get("extraction"),
            result.get("confidence", 0.0),
            result.get("field_confidences", {}),
            result.get("raw_text"),
            result.get("error"),
        )

    return None, 0.0, {}, None, "No content or LLM available"
