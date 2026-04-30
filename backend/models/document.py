from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    PHARMACY_BILL = "PHARMACY_BILL"
    DENTAL_REPORT = "DENTAL_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    POOR = "POOR"
    UNREADABLE = "UNREADABLE"


class MedicineItem(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None


class PrescriptionExtraction(BaseModel):
    doctor_name: Optional[str] = None
    doctor_registration: Optional[str] = None
    patient_name: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    date: Optional[str] = None
    diagnosis: Optional[str] = None
    medicines: List[Union[MedicineItem, str]] = Field(default_factory=list)
    tests_ordered: List[str] = Field(default_factory=list)
    hospital_name: Optional[str] = None


class LineItem(BaseModel):
    description: str
    amount: float


class BillExtraction(BaseModel):
    hospital_name: Optional[str] = None
    patient_name: Optional[str] = None
    date: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    total: Optional[float] = None
    gstin: Optional[str] = None


class LabTest(BaseModel):
    name: str
    result: Optional[str] = None
    unit: Optional[str] = None
    normal_range: Optional[str] = None


class LabReportExtraction(BaseModel):
    lab_name: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    tests: List[LabTest] = Field(default_factory=list)
    remarks: Optional[str] = None
    date: Optional[str] = None


class PharmacyMedicine(BaseModel):
    name: str
    qty: Optional[str] = None
    amount: Optional[float] = None


class PharmacyBillExtraction(BaseModel):
    pharmacy_name: Optional[str] = None
    patient_name: Optional[str] = None
    date: Optional[str] = None
    medicines: List[PharmacyMedicine] = Field(default_factory=list)
    total: Optional[float] = None
    discount: Optional[float] = None
    net_amount: Optional[float] = None


class DentalReportExtraction(BaseModel):
    dentist_name: Optional[str] = None
    patient_name: Optional[str] = None
    date: Optional[str] = None
    procedure: Optional[str] = None
    tooth_numbers: List[str] = Field(default_factory=list)
    materials_used: List[str] = Field(default_factory=list)
    total: Optional[float] = None


class DiagnosticReportExtraction(BaseModel):
    center_name: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    date: Optional[str] = None
    modality: Optional[str] = None  # X-Ray, MRI, CT Scan, etc.
    body_part: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None


class DischargeSummaryExtraction(BaseModel):
    hospital_name: Optional[str] = None
    patient_name: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    procedures: List[str] = Field(default_factory=list)
    discharge_condition: Optional[str] = None
    follow_up: Optional[str] = None
    total_bill: Optional[float] = None


ExtractionResult = Union[
    PrescriptionExtraction,
    BillExtraction,
    LabReportExtraction,
    PharmacyBillExtraction,
    DentalReportExtraction,
    DiagnosticReportExtraction,
    DischargeSummaryExtraction,
]


class DocumentExtractionResult(BaseModel):
    file_id: str
    document_type: DocumentType
    extraction: Optional[ExtractionResult] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_text: Optional[str] = None
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    error: Optional[str] = None


class ClassifiedDocument(BaseModel):
    file_id: str
    file_name: str
    detected_type: DocumentType
    quality: DocumentQuality
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DocVerificationResult(BaseModel):
    status: str  # "passed" | "failed"
    classified_documents: List[ClassifiedDocument] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)
    quality_issues: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
