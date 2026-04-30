# Component Contracts — Plum Claims Processing System

Every significant component is specified precisely enough that another engineer could reimplement it from this document without reading the source code. All signatures are taken directly from the implementation.

---

## 1. Agent 1: Document Verification

**File**: `backend/agents/document_verification.py`

### Purpose
Verify that the correct document types were submitted for the claim category, and that all documents are readable.

### Interface
```python
async def run_document_verification(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `documents` | `List[UploadedDocument]` | Submitted documents. May be empty. |
| `claim_category` | `str` | Uppercase category string, e.g. `"CONSULTATION"` |
| `policy_loader` | `PolicyLoader` | Loaded policy terms, used to get required doc types |
| `llm_service` | `LLMService` | Used to classify real documents; skipped if `actual_type` is set |

Each `UploadedDocument` has:
- `file_id: str` — unique identifier
- `file_name: str` — display name
- `file_content: str` — base64-encoded image (empty for test cases)
- `actual_type: Optional[str]` — if set, skips LLM classification entirely
- `quality: Optional[str]` — if set, skips LLM quality assessment
- `content: Optional[Dict]` — pre-populated extraction data (test cases only)

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `doc_verification_result` | `DocVerificationResult` | Full verification result |
| `pipeline_stop` | `bool` | Set to `True` on failure; routes pipeline to Agent 6 |

`DocVerificationResult` fields:
- `status: str` — `"passed"` or `"failed"`
- `classified_documents: List[ClassifiedDocument]` — each doc with detected type, quality, confidence
- `missing_documents: List[str]` — document type strings that were required but not found
- `quality_issues: List[str]` — filenames of unreadable documents
- `error_message: Optional[str]` — actionable error for the member (never generic)

### Error Conditions

| Condition | `status` | `pipeline_stop` | `error_message` |
|-----------|----------|-----------------|-----------------|
| No documents uploaded | `"failed"` | `True` | "No documents were submitted with this claim." |
| Any document is `UNREADABLE` | `"failed"` | `True` | Names the specific file(s) and instructs re-upload |
| Required doc type missing | `"failed"` | `True` | Names the uploaded types and the missing required type |
| All required types present, quality OK | `"passed"` | unchanged (`False`) | `None` |

### Example

Input: Consultation claim with two PRESCRIPTION documents (no HOSPITAL_BILL).
```
Required: [PRESCRIPTION, HOSPITAL_BILL]
Uploaded: [PRESCRIPTION, PRESCRIPTION]
Missing:  [HOSPITAL_BILL]
```
Output:
```python
DocVerificationResult(
    status="failed",
    classified_documents=[...],
    missing_documents=["HOSPITAL_BILL"],
    error_message="You uploaded 2 Prescriptions but no Hospital Bill. "
                  "A Consultation claim requires: Prescription, Hospital Bill. "
                  "Please upload your Hospital Bill and resubmit."
)
pipeline_stop = True
```

---

## 2. Agent 2: Document Extraction

**File**: `backend/agents/document_extraction.py`

### Purpose
Extract structured data from each verified document, either from pre-populated test content or via GPT-4o Vision.

### Interface
```python
async def run_document_extraction(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `documents` | `List[UploadedDocument]` | Same documents as Agent 1 |
| `doc_verification_result` | `DocVerificationResult` | Used to look up detected type per `file_id` |
| `llm_service` | `LLMService` | Called for each document without pre-populated content |
| `simulate_component_failure` | `bool` | If `True`, fails extraction on the first document deliberately |

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `extraction_results` | `List[DocumentExtractionResult]` | One entry per document |
| `_component_failed` | `bool` | Set to `True` if any document failed extraction |

`DocumentExtractionResult` fields:
- `file_id: str`
- `document_type: DocumentType`
- `extraction: Optional[ExtractionResult]` — typed struct (see below); `None` if extraction failed
- `confidence: float` — 0.0–1.0; 1.0 for pre-populated content, LLM-reported for real docs
- `error: Optional[str]` — error string if extraction failed

`ExtractionResult` is a union of seven typed models:

| Document Type | Model | Key Fields |
|---------------|-------|------------|
| `PRESCRIPTION` | `PrescriptionExtraction` | `doctor_name`, `doctor_registration`, `patient_name`, `diagnosis`, `medicines`, `tests_ordered` |
| `HOSPITAL_BILL` | `BillExtraction` | `hospital_name`, `patient_name`, `line_items: List[LineItem]`, `total` |
| `LAB_REPORT` | `LabReportExtraction` | `patient_name`, `tests: List[LabTest]`, `remarks` |
| `PHARMACY_BILL` | `PharmacyBillExtraction` | `patient_name`, `medicines: List[PharmacyMedicine]`, `total`, `net_amount` |
| `DENTAL_REPORT` | `DentalReportExtraction` | `patient_name`, `procedure`, `tooth_numbers`, `total` |
| `DIAGNOSTIC_REPORT` | `DiagnosticReportExtraction` | `patient_name`, `modality`, `body_part`, `findings`, `impression` |
| `DISCHARGE_SUMMARY` | `DischargeSummaryExtraction` | `patient_name`, `diagnosis`, `procedures`, `total_bill` |

### Error Conditions

| Condition | Behaviour |
|-----------|-----------|
| `simulate_component_failure=True`, first document | Records error, sets `_component_failed=True`, **continues** — never sets `pipeline_stop` |
| LLM API failure (all retries exhausted) | Records error in `DocumentExtractionResult.error`, sets `_component_failed=True`, continues |
| Pre-populated `content` present | Maps content directly to typed model, skips LLM, `confidence=1.0` |
| `file_content` is empty and no `content` | `extraction=None`, `confidence=0.0`, `error="No content or LLM available"` |

**Critical invariant**: Agent 2 never sets `pipeline_stop`. The pipeline always continues after extraction, regardless of failures.

### Example

Input: Hospital bill with `content={"hospital_name": "City Clinic", "patient_name": "Rajesh Kumar", "line_items": [{"description": "Consultation Fee", "amount": 1000}], "total": 1000}`.

Output:
```python
DocumentExtractionResult(
    file_id="F008",
    document_type=DocumentType.HOSPITAL_BILL,
    extraction=BillExtraction(
        hospital_name="City Clinic",
        patient_name="Rajesh Kumar",
        line_items=[LineItem(description="Consultation Fee", amount=1000.0)],
        total=1000.0,
    ),
    confidence=1.0,
    error=None,
)
```

---

## 3. Agent 3: Cross-Validation

**File**: `backend/agents/cross_validation.py`

### Purpose
Verify consistency across all extracted documents — patient name, dates, and amounts.

### Interface
```python
async def run_cross_validation(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `extraction_results` | `List[DocumentExtractionResult]` | All extraction results from Agent 2 |
| `claimed_amount` | `float` | Original claimed amount from submission |
| `member_id` | `str` | Used to look up the policy member's name |
| `policy_loader` | `PolicyLoader` | Used to get member name for advisory check |

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `cross_validation_result` | `CrossValidationResult` | Full validation result |
| `pipeline_stop` | `bool` | Set to `True` only if patient names across documents conflict |

`CrossValidationResult` fields:
- `status: str` — `"passed"` or `"failed"`
- `patient_name_match: bool` — whether all named documents share the same patient
- `date_match: bool` — whether dates across documents are consistent (advisory)
- `amount_match: bool` — whether billed total is within 5% of claimed amount (advisory)
- `member_name_match: bool` — whether patient name matches policy member name (advisory)
- `mismatches: List[Dict]` — list of specific mismatch records
- `error_message: Optional[str]` — set only on hard failure (name mismatch)

### Name Matching Logic

`_names_match(a, b)` returns `True` if:
- Either string is empty (treated as non-contradictory)
- Case-insensitive equality after whitespace normalisation
- One normalised string contains the other (allows "Mr Rajesh Kumar" to match "Rajesh Kumar")

Returns `False` only if both names are non-empty and neither contains the other.

### Error Conditions

| Condition | `status` | `pipeline_stop` | Action |
|-----------|----------|-----------------|--------|
| Patient names conflict across documents | `"failed"` | `True` | `error_message` names both patients and their document types |
| Member name does not match document names | `"passed"` | unchanged | Advisory mismatch recorded, confidence reduced by 0.10 in Agent 6 |
| Date mismatch between documents | `"passed"` | unchanged | Advisory mismatch recorded, confidence reduced by 0.05 in Agent 6 |
| Bill total differs from claimed amount by > 5% | `"passed"` | unchanged | Advisory mismatch recorded, confidence reduced by 0.05 in Agent 6 |
| No extraction results available | `"passed"` | unchanged | Returns pass (no data to contradict) |

### Example

Input: Prescription with `patient_name="Rajesh Kumar"`, Hospital Bill with `patient_name="Arjun Mehta"`.

Output:
```python
CrossValidationResult(
    status="failed",
    patient_name_match=False,
    mismatches=[{
        "type": "patient_name_mismatch",
        "doc_a": "Prescription",
        "name_a": "Rajesh Kumar",
        "doc_b": "Hospital Bill",
        "name_b": "Arjun Mehta"
    }],
    error_message="Patient name mismatch across documents: the Prescription is issued to "
                  "'Rajesh Kumar' but the Hospital Bill is for 'Arjun Mehta'. Please ensure "
                  "all documents belong to the same patient and resubmit."
)
pipeline_stop = True
```

---

## 4. Agent 4: Policy Evaluation

**File**: `backend/agents/policy_evaluation.py`

### Purpose
Apply all insurance policy rules deterministically. No LLM calls. Determines APPROVED, PARTIAL, or REJECTED and computes the final approved amount.

### Interface
```python
async def run_policy_evaluation(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `member_id` | `str` | Member to look up in policy |
| `claim_category` | `str` | Uppercase category string |
| `treatment_date` | `date` | Date of treatment |
| `submission_date` | `date` | Date of claim submission (defaults to `treatment_date`) |
| `claimed_amount` | `float` | Amount claimed |
| `hospital_name` | `Optional[str]` | Used for network hospital discount check |
| `ytd_claims_amount` | `float` | Year-to-date OPD claims already paid |
| `extraction_results` | `List[DocumentExtractionResult]` | Used to extract diagnosis, line items, test names |
| `diagnosis` | `Optional[str]` | Direct diagnosis override (used by test cases) |
| `policy_loader` | `PolicyLoader` | Source of all policy rules |

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `policy_eval_result` | `PolicyEvalResult` | Full result with all check outcomes |

`PolicyEvalResult` fields:
- `member_eligible: MemberEligibilityResult` — `{passed: bool, details: str}`
- `within_submission_deadline: SubmissionDeadlineResult` — `{passed: bool, details: str}`
- `minimum_amount_met: bool`
- `waiting_period_check: WaitingPeriodResult` — `{passed, condition, required_days, actual_days, eligible_date}`
- `exclusion_check: ExclusionCheckResult` — `{passed, excluded_items: [{item, reason}]}`
- `pre_auth_check: PreAuthCheckResult` — `{passed, details}`
- `limit_checks: LimitChecks` — `{per_claim, sub_limit, annual}` each with `{passed, limit, claimed/amount/ytd}`
- `financial_calculation: FinancialCalculation` — `{claimed_amount, network_discount, after_discount, copay_amount, after_copay, sub_limit_cap, approved_amount, breakdown}`
- `line_item_results: List[LineItemResult]` — per-line-item approved/rejected (dental and PARTIAL cases)
- `overall_decision: Decision` — `APPROVED`, `PARTIAL`, or `REJECTED`
- `rejection_reasons: List[str]` — all rejection reason strings

### Financial Calculation Order (critical)
```
1. Start with claimed_amount
2. If hospital is in network_hospitals list → apply network_discount_percent
   after_discount = claimed_amount × (1 - network_discount_percent / 100)
3. Apply copay
   copay_amount = after_discount × (copay_percent / 100)
   after_copay = after_discount - copay_amount
4. Apply sub-limit cap
   approved_amount = min(after_copay, sub_limit)
```

Network discount is always applied before co-pay. Applying them in reverse order produces a different (incorrect) result.

### Policy Rules from `policy_terms.json`
- `coverage.per_claim_limit`: ₹5,000
- `coverage.annual_opd_limit`: ₹50,000
- `submission_rules.deadline_days_from_treatment`: 30
- `submission_rules.minimum_claim_amount`: ₹500
- `waiting_periods.specific_conditions`: diabetes 90d, hernia 365d, obesity_treatment 365d, etc.
- `exclusions.conditions`: "Obesity and weight loss programs", "Cosmetic or aesthetic procedures", etc.
- `opd_categories.dental.excluded_procedures`: "Teeth Whitening", "Veneers", etc.

### Error Conditions

| Condition | `overall_decision` | Notes |
|-----------|-------------------|-------|
| Member not found | `REJECTED` | Pipeline stops immediately |
| Within waiting period | `REJECTED` | Includes eligible_date in reason |
| Excluded condition | `REJECTED` | Full claim rejected |
| Pre-auth missing for high-value diagnostic | `REJECTED` | Instructions to obtain pre-auth included |
| Claimed > per-claim limit | `REJECTED` | States exact limit and claimed amount |
| Some line items excluded (dental) | `PARTIAL` | `approved_amount` = sum of non-excluded items |
| All checks pass | `APPROVED` | Financial calculation applied |

---

## 5. Agent 5: Fraud Detection

**File**: `backend/agents/fraud_detection.py`

### Purpose
Identify suspicious claim patterns using frequency and value analysis against the member's claims history.

### Interface
```python
async def run_fraud_detection(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `treatment_date` | `date` | Date of the current claim |
| `claimed_amount` | `float` | Amount of the current claim |
| `claims_history` | `List[PriorClaim]` | Previous claims for this member |
| `policy_loader` | `PolicyLoader` | Source of fraud threshold configuration |

`PriorClaim` has `claim_id`, `date`, `amount`, `provider`. Accepts both Pydantic objects and raw dicts.

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `fraud_result` | `FraudResult` | Fraud score, flags, and recommendation |

`FraudResult` fields:
- `fraud_score: float` — 0.0–1.0 composite score
- `flags: List[FraudFlag]` — each with `flag_type`, `details`, `severity` (`"low"/"medium"/"high"`)
- `same_day_count: int` — number of prior claims on the same treatment date
- `monthly_count: int` — number of prior claims in the same month
- `is_high_value: bool` — whether claimed_amount > ₹25,000
- `recommendation: str` — `"CLEAR"` or `"MANUAL_REVIEW"`

### Fraud Signals and Score Contributions
| Signal | Threshold | Score delta | Severity | Flag type |
|--------|-----------|-------------|----------|-----------|
| Same-day claims | ≥ 2 prior on same date | +0.50 | HIGH | `MULTIPLE_SAME_DAY_CLAIMS` |
| Monthly frequency | ≥ 6 in same month | +0.30 | MEDIUM | `EXCESSIVE_MONTHLY_CLAIMS` |
| High-value claim | > ₹25,000 | +0.20 | MEDIUM | `HIGH_VALUE_CLAIM` |
| Round amount | > ₹1,000 and divisible by 1,000 | +0.05 | LOW | `ROUND_AMOUNT` |

### Routing Decision
- Same-day limit violation present → `MANUAL_REVIEW` (regardless of total score)
- `fraud_score ≥ 0.80` → `MANUAL_REVIEW`
- Otherwise → `CLEAR`

**Important**: Fraud detection never sets `pipeline_stop`. Agent 6 reads the recommendation and applies priority logic. The system never auto-rejects on fraud grounds alone.

### Example

Input: `claims_history` = 3 claims on `treatment_date = 2024-10-30`.
```
same_day_count = 3  (≥ 2 limit)
fraud_score = 0.50 + (round 4800→ +0.05) = 0.55
```
Output:
```python
FraudResult(
    fraud_score=0.55,
    flags=[
        FraudFlag(flag_type="MULTIPLE_SAME_DAY_CLAIMS",
                  details="3 previous claims found on 2024-10-30 (limit is 2 per day). "
                          "This is claim #4 today.",
                  severity="high"),
        FraudFlag(flag_type="ROUND_AMOUNT",
                  details="Claimed amount ₹4,800 is a round number — minor signal.",
                  severity="low"),
    ],
    same_day_count=3,
    monthly_count=3,
    is_high_value=False,
    recommendation="MANUAL_REVIEW",
)
```

---

## 6. Agent 6: Decision Aggregation

**File**: `backend/agents/decision_aggregation.py`

### Purpose
Produce the final `ClaimDecision` by combining all agent results in priority order with a calculated confidence score.

### Interface
```python
async def run_decision_aggregation(state: Dict[str, Any]) -> Dict[str, Any]
```

### Input (from `state`)
| Key | Type | Description |
|-----|------|-------------|
| `doc_verification_result` | `Optional[DocVerificationResult]` | From Agent 1 |
| `cross_validation_result` | `Optional[CrossValidationResult]` | From Agent 3 |
| `policy_eval_result` | `Optional[PolicyEvalResult]` | From Agent 4 |
| `fraud_result` | `Optional[FraudResult]` | From Agent 5 |
| `_component_failed` | `bool` | Set by Agent 2 on extraction failure |
| `claimed_amount` | `float` | Original claimed amount |

### Output (keys added to returned state)
| Key | Type | Description |
|-----|------|-------------|
| `final_decision` | `ClaimDecision` | Final verdict |

`ClaimDecision` fields:
- `decision: Decision` — `APPROVED`, `PARTIAL`, `REJECTED`, or `MANUAL_REVIEW`
- `approved_amount: float` — ₹ amount approved; 0.0 for rejections and manual review
- `confidence_score: float` — 0.10–1.00
- `reasons: List[str]` — human-readable decision reasons
- `recommendations: List[str]` — actions for the member or ops team
- `errors: List[str]` — processing errors that affected the decision

### Decision Priority (highest priority wins)
1. `doc_verification_result.status == "failed"` → `MANUAL_REVIEW` (stopped_early)
2. `cross_validation_result.status == "failed"` → `MANUAL_REVIEW` (stopped_early)
3. `fraud_result.recommendation == "MANUAL_REVIEW"` → `MANUAL_REVIEW`
4. `policy_eval_result.overall_decision` → drives the final decision

### Confidence Calculation
Starting from 1.0:
- `_component_failed=True`: −0.20
- `!cross_result.amount_match`: −0.05
- `!cross_result.date_match`: −0.05
- `!cross_result.member_name_match`: −0.10
- `fraud_result.recommendation == "MANUAL_REVIEW"`: −0.25
- Clear policy rejection (keyword: exclusion/waiting period/limit/not found): override to 0.95
- Minimum floor: 0.10

### Example — TC011 (Component Failure)
```python
ClaimDecision(
    decision=Decision.APPROVED,
    approved_amount=4000.0,
    confidence_score=0.80,  # 1.0 - 0.20 (component_failed)
    reasons=[
        "Claim meets all policy criteria. Financial breakdown: ...",
        "Note: one or more documents could not be extracted. Decision is based on partial data."
    ],
    recommendations=[
        "Manual review recommended: incomplete document extraction due to component failure."
    ],
    errors=["One or more extraction components failed during processing."]
)
```

---

## 7. Claims Pipeline

**File**: `backend/orchestrator/pipeline.py`

### Purpose
The public entry point for claim processing. Initialises the LangGraph state machine, runs all agents, and returns a complete `ClaimResponse`.

### Interface
```python
class ClaimsPipeline:
    def __init__(self) -> None
    async def process(self, submission: ClaimSubmission) -> ClaimResponse
```

### `__init__`
Compiles the LangGraph graph once (singleton via `_COMPILED_GRAPH`). Initialises `PolicyLoader` from `settings.POLICY_FILE_PATH` and `LLMService`. Both are injected into `ClaimState` on each `process()` call.

### `process(submission)` Input

`ClaimSubmission` fields (all validated by Pydantic before reaching the pipeline):
| Field | Type | Constraint |
|-------|------|------------|
| `member_id` | `str` | Non-empty |
| `policy_id` | `str` | e.g. `"PLUM_GHI_2024"` |
| `claim_category` | `ClaimCategory` | Enum: CONSULTATION, DIAGNOSTIC, PHARMACY, DENTAL, VISION, ALTERNATIVE_MEDICINE |
| `treatment_date` | `date` | ISO date |
| `claimed_amount` | `float` | Must be > 0 (enforced by `field_validator`) |
| `hospital_name` | `Optional[str]` | Used for network discount check |
| `diagnosis` | `Optional[str]` | Direct diagnosis shortcut; bypasses prescription extraction |
| `submission_date` | `Optional[date]` | Defaults to `treatment_date` if `None` |
| `documents` | `List[UploadedDocument]` | Can be empty (caught by Agent 1) |
| `claims_history` | `Optional[List[PriorClaim]]` | Fraud detection input |
| `ytd_claims_amount` | `Optional[float]` | Defaults to 0.0 |
| `simulate_component_failure` | `Optional[bool]` | Defaults to `False` |

### `process(submission)` Output

`ClaimResponse` fields:
| Field | Type | Description |
|-------|------|-------------|
| `claim_id` | `str` | `"CLM-{8 uppercase hex chars}"`, e.g. `"CLM-A3F2B1C4"` |
| `status` | `str` | `"completed"` or `"stopped_early"` |
| `decision` | `Optional[str]` | `"APPROVED"`, `"PARTIAL"`, `"REJECTED"`, `"MANUAL_REVIEW"`, or `None` |
| `approved_amount` | `Optional[float]` | `None` for rejections and stopped_early |
| `confidence_score` | `float` | 0.10–1.00 |
| `reasons` | `List[str]` | Decision reasons |
| `trace` | `DecisionTrace` | Full pipeline audit log |
| `errors` | `List[str]` | Processing errors |
| `recommendations` | `List[str]` | Member/ops actions |
| `error_message` | `Optional[str]` | Most specific error for display (surfaced from Agent 1 or Agent 3 on failure) |

`DecisionTrace` fields:
- `entries: List[TraceEntry]` — one per agent that ran
- `total_duration_ms: float` — wall-clock time for the entire pipeline
- `pipeline_status: str` — `"completed"` or `"stopped_early"`

### Error Conditions
| Condition | Behaviour |
|-----------|-----------|
| Pydantic validation fails (`claimed_amount ≤ 0`, missing required field) | Raises `ValueError` before pipeline starts; FastAPI returns HTTP 422 |
| Individual agent raises unhandled exception | `_timed_node` catches it, sets `pipeline_stop=True`, records in trace, routes to Agent 6 |
| `graph.ainvoke()` itself raises | Pipeline catches it, returns `stopped_early` response with error in `errors` list |
| Policy file not found at startup | `PolicyLoader` logs warning and uses empty policy; all member checks will fail |

---

## 8. LLM Service

**File**: `backend/services/llm_service.py`

### Purpose
Wraps the OpenAI Python SDK (`AsyncOpenAI`) to classify documents and extract structured data. Handles retries and timeouts.

### Interface
```python
class LLMService:
    async def classify_document(self, file_content: str) -> Dict[str, Any]
    async def extract_document(self, file_content: str, doc_type: DocumentType) -> Dict[str, Any]
```

### `classify_document(file_content)`

**Input**: `file_content: str` — base64-encoded image or data URI.

**Output** (`Dict[str, Any]`):
- `document_type: DocumentType` — classified type
- `quality: DocumentQuality` — `GOOD`, `POOR`, or `UNREADABLE`
- `confidence: float` — 0.0–1.0 as reported by the model

**Prompt**: Instructs GPT-4o to return `{"document_type": "...", "quality": "...", "confidence": 0.0}`. Uses `response_format={"type": "json_object"}`.

**Retry**: `LLM_MAX_RETRIES=2` with exponential backoff. On exhaustion, returns `{"document_type": DocumentType.UNKNOWN, "quality": DocumentQuality.POOR, "confidence": 0.0}`.

### `extract_document(file_content, doc_type)`

**Input**:
- `file_content: str` — base64-encoded image
- `doc_type: DocumentType` — determines which extraction prompt and target model to use

**Output** (`Dict[str, Any]`):
- `extraction: Optional[ExtractionResult]` — typed Pydantic model instance, or `None` on failure
- `confidence: float` — 0.0–1.0
- `field_confidences: Dict[str, float]` — per-field confidence (not always populated)
- `raw_text: Optional[str]` — raw LLM response text for debugging
- `error: Optional[str]` — error string if extraction failed

**Extraction models by type**: Uses one of eight `_EXTRACTION_MODELS` entries keyed by `DocumentType`. The prompt is type-specific (different fields asked for prescription vs. hospital bill vs. lab report).

**Retry**: Same as `classify_document`. On exhaustion, returns `{"extraction": None, "confidence": 0.0, "error": "<error message>"}`.

---

## 9. Policy Loader

**File**: `backend/services/policy_loader.py`

### Purpose
Loads `policy_terms.json` at startup and provides typed accessor methods for all policy data. All agents read through this interface rather than directly from the JSON.

### Interface

```python
class PolicyLoader:
    def __init__(self, policy_file_path: str) -> None

    # Member accessors
    def get_member(self, member_id: str) -> Optional[MemberInfo]
    def get_member_raw(self, member_id: str) -> Optional[Dict[str, Any]]
    def get_all_members(self) -> List[MemberInfo]
    def get_member_join_date(self, member_id: str) -> Optional[str]

    # Document requirements
    def get_document_requirements(self, category: str) -> Dict[str, List[str]]
    # Returns: {"required": ["PRESCRIPTION", "HOSPITAL_BILL"], "optional": ["LAB_REPORT"]}

    # Category configuration
    def get_category_config(self, category: str) -> Dict[str, Any]
    def get_all_categories(self) -> Dict[str, Any]
    def get_category_exclusions(self, category: str) -> List[str]
    def get_category_covered_procedures(self, category: str) -> List[str]

    # Waiting periods
    def get_initial_waiting_period(self) -> int
    def get_waiting_period(self, condition_key: str) -> Optional[int]
    def get_waiting_period_for_diagnosis(self, diagnosis: str) -> Tuple[Optional[str], int]
    # Returns: (matched_condition_key, waiting_days)
    # e.g. ("diabetes", 90) or (None, 30) for unmatched diagnoses

    # Exclusions
    def get_excluded_conditions_list(self) -> List[str]
    def is_excluded_condition(self, text: str) -> bool
    def get_matching_exclusion(self, text: str) -> Optional[str]
    def is_excluded_procedure(self, category: str, procedure: str) -> bool
    def get_exclusions(self) -> Dict[str, Any]

    # Limits
    def get_annual_limit(self) -> float           # 50000.0
    def get_per_claim_limit(self) -> float         # 5000.0
    def get_minimum_claim_amount(self) -> float    # 500.0
    def get_submission_deadline_days(self) -> int  # 30

    # Network / fraud / pre-auth
    def is_network_hospital(self, hospital_name: str) -> bool
    def get_network_hospitals(self) -> List[str]
    def get_fraud_thresholds(self) -> Dict[str, Any]
    def get_submission_rules(self) -> Dict[str, Any]
    def get_pre_auth_rules(self) -> Dict[str, Any]
    def raw(self) -> Dict[str, Any]
```

### `get_waiting_period_for_diagnosis` Detail

Uses `_CONDITION_KEYWORD_MAP` to fuzzy-match free-text diagnosis against known conditions. Example keyword lists:
- `"diabetes"` matches: `"diabetes"`, `"t2dm"`, `"dm "`, `"diabetic"`, `"diabetes mellitus"`, `"type 2 diabetes"`
- `"obesity_treatment"` matches: `"obesity"`, `"bariatric"`, `"weight loss program"`, `"morbid obese"`
- `"hernia"` matches: `"hernia"`, `"herniation"`

If no keyword matches, returns `(None, initial_waiting_period_days)` (30 days).

### `is_excluded_condition` Detail

Matches `text` against the `exclusions.conditions` list using:
1. Substring containment (either direction)
2. Meaningful word overlap: any word ≥ 5 characters (excluding stop words) that appears in both strings

Example: `"Morbid Obesity — BMI 37"` matches `"Obesity and weight loss programs"` because `"obesity"` (7 chars) appears in both.

---

## 10. API Endpoints

**File**: `backend/main.py`

All endpoints are served by FastAPI on port 8000 (local) or `$PORT` (Railway).

### `POST /api/claims/submit`

**Request body**: `ClaimSubmission` (JSON)

**Response**: `ClaimResponse` (JSON)

**Status codes**:
- `200 OK` — pipeline ran (even if decision is REJECTED or stopped_early)
- `422 Unprocessable Entity` — Pydantic validation failed (malformed body)
- `500 Internal Server Error` — unhandled exception in pipeline

**Side effect**: On success, stores result in `claims_store[claim_id]` (in-memory).

### `GET /api/claims/{claim_id}`

**Path param**: `claim_id: str`

**Response**: `ClaimResponse`

**Status codes**:
- `200 OK` — found
- `404 Not Found` — `claim_id` not in `claims_store`

### `GET /api/claims`

**Response**: `List[Dict]` — lightweight summaries of all processed claims:
```json
[{"claim_id": "CLM-A3F2B1C4", "status": "completed", "decision": "APPROVED",
  "approved_amount": 1350.0, "confidence_score": 1.0}]
```

### `GET /api/policy/members`

**Response**: `List[Dict]` — all `MemberInfo` records from `policy_terms.json`.

### `GET /api/policy/categories`

**Response**: `Dict[str, Dict]` — all OPD category configs with document requirements:
```json
{"CONSULTATION": {"config": {...}, "document_requirements": {"required": [...], "optional": [...]}}}
```

### `POST /api/eval/run`

**Request body**: Empty (no body required)

**Response**:
```json
{
  "total": 12, "passed": 12, "failed": 0,
  "results": [
    {"case_id": "TC001", "case_name": "...", "expected_decision": null,
     "actual_decision": "MANUAL_REVIEW", "passed": true, "duration_ms": 45, ...}
  ]
}
```
Runs all 12 test cases synchronously and returns aggregated results.

### `GET /api/eval/test-cases`

**Response**: Raw `test_cases.json` content — used by the frontend to populate the test scenario loader dropdown.

### `POST /api/eval/run-single`

**Request body**: `{"case_id": "TC001"}`

**Response**: Full `ClaimResponse` fields merged with eval metadata:
```json
{
  "claim_id": "CLM-...", "status": "stopped_early", "decision": "MANUAL_REVIEW",
  "case_id": "TC001", "case_name": "Wrong Document Uploaded",
  "expected_decision": null, "expected_amount": null,
  "passed": true, "reason": "ok", "duration_ms": 38,
  "agent_timing": {"DocumentVerification": 35, "DecisionAggregation": 2},
  "trace": {...}
}
```

**Status codes**:
- `200 OK` — case ran
- `404 Not Found` — `case_id` not in `test_cases.json`

### `GET /health`

**Response**: `{"status": "ok", "service": "plum-claims-processor"}`

Used as the Railway healthcheck endpoint.
