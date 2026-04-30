from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIError

from config import settings
from models.document import (
    DocumentQuality,
    DocumentType,
    PrescriptionExtraction,
    BillExtraction,
    LabReportExtraction,
    PharmacyBillExtraction,
    DentalReportExtraction,
    DiagnosticReportExtraction,
    DischargeSummaryExtraction,
)

logger = logging.getLogger(__name__)

_EXTRACTION_MODELS = {
    DocumentType.PRESCRIPTION: PrescriptionExtraction,
    DocumentType.HOSPITAL_BILL: BillExtraction,
    DocumentType.LAB_REPORT: LabReportExtraction,
    DocumentType.PHARMACY_BILL: PharmacyBillExtraction,
    DocumentType.DENTAL_REPORT: DentalReportExtraction,
    DocumentType.DIAGNOSTIC_REPORT: DiagnosticReportExtraction,
    DocumentType.DISCHARGE_SUMMARY: DischargeSummaryExtraction,
}

_CLASSIFY_PROMPT = """You are an AI assistant specialized in Indian medical document analysis.

Analyze this medical document image and return a JSON object with:
- document_type: one of PRESCRIPTION, HOSPITAL_BILL, LAB_REPORT, PHARMACY_BILL, DENTAL_REPORT, DIAGNOSTIC_REPORT, DISCHARGE_SUMMARY, UNKNOWN
- quality: one of GOOD, POOR, UNREADABLE
- confidence: float between 0 and 1

Rules:
- PRESCRIPTION: doctor's handwritten or printed prescription with patient name, diagnosis, medicines
- HOSPITAL_BILL: itemized bill from a hospital/clinic with total amount
- LAB_REPORT: blood/urine/pathology test results with values and normal ranges
- PHARMACY_BILL: bill from a pharmacy/medical shop listing medicines and amounts
- DENTAL_REPORT: dental treatment record with tooth numbers and procedures
- DIAGNOSTIC_REPORT: radiology reports (X-ray, MRI, CT, ultrasound) with findings
- DISCHARGE_SUMMARY: hospital discharge document summarizing inpatient stay

Respond ONLY with valid JSON. Example:
{"document_type": "PRESCRIPTION", "quality": "GOOD", "confidence": 0.92}"""


def _extraction_prompt(doc_type: DocumentType) -> str:
    base = (
        "You are an expert at extracting structured data from Indian medical documents. "
        "Extract all available information from this document image and return ONLY valid JSON. "
        "Use null for fields you cannot find. Be precise with amounts — extract exact numbers.\n\n"
    )
    specific: Dict[DocumentType, str] = {
        DocumentType.PRESCRIPTION: (
            "Extract from this PRESCRIPTION:\n"
            "- doctor_name, doctor_registration (reg number), patient_name, age, gender\n"
            "- date (DD/MM/YYYY format), diagnosis, hospital_name\n"
            "- medicines: list of {name, dosage, frequency, duration}\n"
            "- tests_ordered: list of test names\n"
            'Return JSON matching: {"doctor_name":..., "doctor_registration":..., "patient_name":..., '
            '"age":..., "gender":..., "date":..., "diagnosis":..., "hospital_name":..., '
            '"medicines":[{"name":..., "dosage":..., "frequency":..., "duration":...}], "tests_ordered":[...]}'
        ),
        DocumentType.HOSPITAL_BILL: (
            "Extract from this HOSPITAL BILL:\n"
            "- hospital_name, patient_name, date, gstin\n"
            "- line_items: list of {description, amount} for each line\n"
            "- total: final total amount\n"
            'Return JSON: {"hospital_name":..., "patient_name":..., "date":..., "gstin":..., '
            '"line_items":[{"description":..., "amount":...}], "total":...}'
        ),
        DocumentType.LAB_REPORT: (
            "Extract from this LAB REPORT:\n"
            "- lab_name, patient_name, doctor_name, date, remarks\n"
            "- tests: list of {name, result, unit, normal_range}\n"
            'Return JSON: {"lab_name":..., "patient_name":..., "doctor_name":..., "date":..., '
            '"tests":[{"name":..., "result":..., "unit":..., "normal_range":...}], "remarks":...}'
        ),
        DocumentType.PHARMACY_BILL: (
            "Extract from this PHARMACY BILL:\n"
            "- pharmacy_name, patient_name, date\n"
            "- medicines: list of {name, qty, amount}\n"
            "- total, discount, net_amount\n"
            'Return JSON: {"pharmacy_name":..., "patient_name":..., "date":..., '
            '"medicines":[{"name":..., "qty":..., "amount":...}], "total":..., "discount":..., "net_amount":...}'
        ),
        DocumentType.DENTAL_REPORT: (
            "Extract from this DENTAL REPORT:\n"
            "- dentist_name, patient_name, date, procedure, total\n"
            "- tooth_numbers: list, materials_used: list\n"
            'Return JSON: {"dentist_name":..., "patient_name":..., "date":..., "procedure":..., '
            '"tooth_numbers":[...], "materials_used":[...], "total":...}'
        ),
        DocumentType.DIAGNOSTIC_REPORT: (
            "Extract from this DIAGNOSTIC/RADIOLOGY REPORT:\n"
            "- center_name, patient_name, doctor_name, date, modality, body_part, findings, impression\n"
            'Return JSON: {"center_name":..., "patient_name":..., "doctor_name":..., "date":..., '
            '"modality":..., "body_part":..., "findings":..., "impression":...}'
        ),
        DocumentType.DISCHARGE_SUMMARY: (
            "Extract from this DISCHARGE SUMMARY:\n"
            "- hospital_name, patient_name, admission_date, discharge_date\n"
            "- diagnosis, procedures (list), discharge_condition, follow_up, total_bill\n"
            'Return JSON: {"hospital_name":..., "patient_name":..., "admission_date":..., '
            '"discharge_date":..., "diagnosis":..., "procedures":[...], "discharge_condition":..., '
            '"follow_up":..., "total_bill":...}'
        ),
    }
    return base + specific.get(doc_type, "Extract all available structured data and return as JSON.")


class LLMService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,  # We handle retries ourselves
        )

    async def _call_with_retry(
        self,
        messages: list,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        last_error: Optional[Exception] = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                    temperature=0,
                )
                return response.choices[0].message.content
            except APITimeoutError as exc:
                last_error = exc
                logger.warning("LLM timeout on attempt %d: %s", attempt + 1, exc)
            except RateLimitError as exc:
                last_error = exc
                logger.warning("Rate limit on attempt %d: %s", attempt + 1, exc)
                await asyncio.sleep(2 ** attempt)
            except APIError as exc:
                last_error = exc
                logger.warning("API error on attempt %d: %s", attempt + 1, exc)
            if attempt < settings.LLM_MAX_RETRIES:
                await asyncio.sleep(1)
        logger.error("All LLM attempts failed. Last error: %s", last_error)
        return None

    def _image_message(self, image_base64: str, prompt: str) -> list:
        # Support both raw base64 and data-URI formats
        if image_base64.startswith("data:"):
            image_url = image_base64
        else:
            image_url = f"data:image/jpeg;base64,{image_base64}"
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
                ],
            }
        ]

    async def classify_document(self, image_base64: str) -> Dict[str, Any]:
        messages = self._image_message(image_base64, _CLASSIFY_PROMPT)
        raw = await self._call_with_retry(messages, max_tokens=256)
        if raw is None:
            return {
                "document_type": DocumentType.UNKNOWN,
                "quality": DocumentQuality.POOR,
                "confidence": 0.0,
                "error": "LLM call failed",
            }
        try:
            data = json.loads(raw)
            return {
                "document_type": DocumentType(data.get("document_type", "UNKNOWN")),
                "quality": DocumentQuality(data.get("quality", "POOR")),
                "confidence": float(data.get("confidence", 0.5)),
            }
        except Exception as exc:
            logger.error("Failed to parse classify response: %s | raw=%s", exc, raw)
            return {
                "document_type": DocumentType.UNKNOWN,
                "quality": DocumentQuality.POOR,
                "confidence": 0.0,
                "error": str(exc),
            }

    async def extract_document(
        self, image_base64: str, document_type: DocumentType
    ) -> Dict[str, Any]:
        prompt = _extraction_prompt(document_type)
        messages = self._image_message(image_base64, prompt)
        raw = await self._call_with_retry(messages, max_tokens=2048)
        if raw is None:
            return {"error": "LLM call failed", "confidence": 0.0, "raw_text": None, "extraction": None}
        try:
            data = json.loads(raw)
            model_cls = _EXTRACTION_MODELS.get(document_type)
            extraction = model_cls(**data) if model_cls else data
            field_confidences: Dict[str, float] = {}
            if model_cls:
                for field in model_cls.model_fields:
                    field_confidences[field] = 0.9 if data.get(field) is not None else 0.0
            return {
                "extraction": extraction,
                "confidence": 0.85,
                "raw_text": raw,
                "field_confidences": field_confidences,
            }
        except Exception as exc:
            logger.error("Failed to parse extraction response: %s | raw=%s", exc, raw)
            return {"error": str(exc), "confidence": 0.0, "raw_text": raw, "extraction": None}
