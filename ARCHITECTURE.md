# Architecture Document — Plum Claims Processing System

## 1. System Overview

This is a multi-agent AI system that automates OPD health insurance claim processing end-to-end. It uses 6 specialized agents orchestrated by LangGraph to verify documents, extract information, validate against policy rules, detect fraud, and produce explainable, auditable decisions.

The system processes claims for policy `PLUM_GHI_2024` (ICICI Lombard Group Health Insurance — Standard Plan) covering six OPD categories: Consultation, Diagnostic, Pharmacy, Dental, Vision, and Alternative Medicine.

```
                     ┌──────────────────────────┐
                     │    Claim Submission       │
                     │    (Next.js Frontend)     │
                     │  localhost:3000 / Vercel  │
                     └───────────┬──────────────┘
                                 │ POST /api/claims/submit
                                 │ ClaimSubmission (JSON)
                                 ▼
                     ┌──────────────────────────┐
                     │    FastAPI Backend        │
                     │    localhost:8000 /       │
                     │    Railway               │
                     │                          │
                     │  • Validates input        │
                     │    (Pydantic v2)          │
                     │  • Generates claim_id     │
                     │  • Loads policy terms     │
                     └───────────┬──────────────┘
                                 │
                   ┌─────────────▼─────────────┐
                   │   LangGraph Orchestrator   │
                   │   ClaimsPipeline.process() │
                   │                           │
                   │  Initialises ClaimState,  │
                   │  injects policy_loader &  │
                   │  llm_service into state   │
                   └─────────────┬─────────────┘
                                 │
        ┌────────────────────────▼────────────────────────┐
        │                Agent Pipeline                    │
        │                                                  │
        │  ┌─────────────────────────────────────────┐    │
        │  │ Agent 1: Document Verification           │    │
        │  │ • Classifies doc types (GPT-4o Vision    │    │
        │  │   for real uploads; pre-set for tests)   │    │
        │  │ • Checks quality (GOOD/POOR/UNREADABLE) │    │
        │  │ • Validates required docs per category   │    │
        │  └──────────────┬───────────────────────────┘    │
        │                 │                                 │
        │         pipeline_stop?─────────────────────┐     │
        │                 │ NO                        │     │
        │                 ▼                           │     │
        │  ┌──────────────────────────────────────┐  │     │
        │  │ Agent 2: Document Extraction          │  │     │
        │  │ • GPT-4o Vision → typed structs       │  │     │
        │  │   (PrescriptionExtraction,            │  │     │
        │  │    BillExtraction, etc.)              │  │     │
        │  │ • Graceful degradation on failure     │  │     │
        │  │ • Never sets pipeline_stop            │  │     │
        │  └──────────────┬───────────────────────┘  │     │
        │                 │ always continues          │     │
        │                 ▼                           │     │
        │  ┌──────────────────────────────────────┐  │     │
        │  │ Agent 3: Cross-Validation             │  │     │
        │  │ • Patient name consistency            │  │     │
        │  │ • Date and amount advisory checks     │  │     │
        │  │ • Member name match (advisory)        │  │     │
        │  └──────────────┬───────────────────────┘  │     │
        │                 │                           │     │
        │         pipeline_stop?─────────────────┐   │     │
        │                 │ NO                    │   │     │
        │                 ▼                       │   │     │
        │  ┌──────────────────────────────────┐  │   │     │
        │  │ Agent 4: Policy Evaluation        │  │   │     │
        │  │ • 10 ordered deterministic checks │  │   │     │
        │  │ • Zero LLM calls                  │  │   │     │
        │  │ • Financial calculation           │  │   │     │
        │  └──────────────┬───────────────────┘  │   │     │
        │                 │ always continues      │   │     │
        │                 ▼                       │   │     │
        │  ┌──────────────────────────────────┐  │   │     │
        │  │ Agent 5: Fraud Detection          │  │   │     │
        │  │ • Same-day frequency check        │  │   │     │
        │  │ • Monthly frequency check         │  │   │     │
        │  │ • High-value threshold check      │  │   │     │
        │  │ • Round-amount signal             │  │   │     │
        │  └──────────────┬───────────────────┘  │   │     │
        │                 │ always continues      │   │     │
        │                 ▼                       ▼   ▼     │
        │  ┌──────────────────────────────────────────┐    │
        │  │ Agent 6: Decision Aggregation             │    │
        │  │ • Priority-order resolution               │    │
        │  │ • Confidence calculation                  │    │
        │  │ • Trace assembly                          │    │
        │  │ → APPROVED / PARTIAL / REJECTED /         │    │
        │  │   MANUAL_REVIEW + full DecisionTrace      │    │
        │  └──────────────────────────────────────────┘    │
        └─────────────────────────────────────────────────┘
                                 │
                     ┌───────────▼──────────────┐
                     │     ClaimResponse         │
                     │  claim_id, status,        │
                     │  decision, approved_amt,  │
                     │  confidence, reasons,     │
                     │  trace (full audit log),  │
                     │  recommendations, errors  │
                     └──────────────────────────┘
```

---

## 2. Design Decisions & Rationale

### Why Multi-Agent Architecture

Each agent has exactly one responsibility, which makes the system testable, debuggable, and extensible independently. Practical benefits:

- **Failure isolation**: Agent 2 can fail on one document while the rest of the pipeline continues (TC011). If the entire pipeline were a monolith, any failure would lose the whole decision.
- **Early termination**: Agents 1 and 3 can short-circuit the pipeline before expensive LLM calls are made. If documents are wrong, there is no point invoking GPT-4o for extraction.
- **Independent replaceability**: The extraction agent (GPT-4o Vision) can be swapped for a different vision model without touching policy evaluation or fraud detection.
- **Natural fit**: The workflow maps directly to how a real claims adjuster works — verify docs exist → read them → check consistency → apply policy → flag fraud → decide.

### Why LangGraph for Orchestration

LangGraph provides a typed state graph where each agent node reads from and writes to a shared `ClaimState` dict. Key properties:

- **Conditional edges**: After Agent 1, the graph routes to either Agent 2 (docs OK) or directly to Agent 6 (docs failed). This is a first-class LangGraph feature.
- **Immutable state**: Each node returns a new state dict (`{**state, "new_key": value}`), not a mutation. This makes the data flow traceable and testable.
- **Error handling per node**: Each agent is wrapped in `_timed_node()`, which catches all exceptions, records them in the trace, and either continues or stops the pipeline, depending on the severity.

**Alternative considered — CrewAI**: Designed for autonomous, role-playing agents that negotiate tasks. Claims processing needs *deterministic, controlled* sequential flow — not autonomy. Rejected.

**Alternative considered — plain async function chain**: No state management, no conditional routing, no built-in error recovery per step. Every exception would require manual branching. Rejected.

### Why Deterministic Policy Engine (No LLM in Agent 4)

Agent 4 contains zero LLM calls. This is deliberate:

- **Precision**: Insurance policy rules are exact. The per-claim limit is ₹5,000, not "approximately ₹5,000". An LLM cannot reliably produce the exact same calculation on every invocation.
- **Auditability**: Regulators, insurers, and members need to understand exactly why a claim was approved or rejected. A deterministic trace — "claimed ₹7,500 > per-claim limit ₹5,000 → REJECTED" — is auditable. An LLM's reasoning is not.
- **Cost and latency**: Policy evaluation runs 10 checks in under 1ms. Adding LLM calls here would add 1–3 seconds per claim and ~₹0.02 per call.
- **Financial correctness**: Calculation order matters. Network discount is applied first, then co-pay on the discounted amount. `₹4,500 × 80% = ₹3,600 → ₹3,600 × 90% = ₹3,240`. Getting this wrong by applying co-pay first produces a different number. This must be exactly right every time.

**Alternative considered — LLM-based policy evaluation**: Rejected. Non-deterministic output, impossible to audit, incorrect on edge cases, expensive.

### Why GPT-4o Vision for Document Processing

Indian medical documents present extreme variation: handwritten prescriptions in regional scripts, rubber-stamped hospital bills, phone photos of crumpled receipts. Traditional approaches fail here:

- **Single-call efficiency**: GPT-4o classifies the document type AND extracts all structured fields in one API call per document, with type-specific extraction prompts.
- **Handles variability**: OCR + rule-based parsing would require preprocessing pipelines and would break on handwriting. GPT-4o handles all of this natively.
- **Structured output mode**: The prompts instruct GPT-4o to return only valid JSON, which maps directly to typed Pydantic models (`PrescriptionExtraction`, `BillExtraction`, etc.).

**Alternative considered — Tesseract OCR + rule-based parser**: Would require preprocessing (image cleaning, deskewing), a separate document classifier, and hand-written parsers per document type. Would fail on handwriting. Rejected.

**Alternative considered — Google Cloud Vision**: Viable, but adds another vendor dependency. GPT-4o handles classification + extraction in one pass. Rejected for simplicity.

### Why Separate Backend and Frontend

- The AI/ML stack (LangGraph, OpenAI SDK, Pydantic) is a Python ecosystem. The frontend is Next.js/TypeScript.
- A clean API boundary (`POST /api/claims/submit → ClaimResponse`) means either side can be rebuilt independently.
- The backend can serve other clients (internal ops dashboard, mobile app) without change.
- Deployment targets differ: Railway (container) for the backend, Vercel (edge CDN) for the frontend.

---

## 3. Component Architecture

### 3.1 Agent 1: Document Verification

**File**: `backend/agents/document_verification.py`

**Purpose**: Gate the pipeline early. Catch missing, wrong, or unreadable documents before any LLM extraction is attempted.

**Logic flow**:
1. If no documents uploaded → fail immediately.
2. For each document: if `actual_type` is pre-set (test cases), use it directly. Otherwise, call `llm_service.classify_document(file_content)` to determine type and quality via GPT-4o Vision.
3. If any document is `UNREADABLE` → fail with the specific filename.
4. Compare detected types against `policy_loader.get_document_requirements(category)`. If required types are missing → fail with a message naming both what was uploaded and what is needed.
5. If all checks pass → write `doc_verification_result` to state with status `"passed"`.

**Key design**: Error messages are always actionable. "You uploaded 2 Prescriptions but no Hospital Bill. A Consultation claim requires: Prescription, Hospital Bill. Please upload your Hospital Bill and resubmit." — never a generic failure.

**Short-circuit**: Sets `pipeline_stop=True` on failure. LangGraph routes directly to Agent 6.

### 3.2 Agent 2: Document Extraction

**File**: `backend/agents/document_extraction.py`

**Purpose**: Convert document images (or pre-populated test data) into typed structured records.

**Logic flow**:
1. For each verified document: if `doc.content` is set (test cases), map it directly to the appropriate extraction model (`_map_content_to_extraction`). No LLM call.
2. Otherwise, call `llm_service.extract_document(file_content, doc_type)` with a type-specific prompt (8 different prompts, one per document type).
3. If `simulate_component_failure=True` and this is the first document → record an error for that document and set `_component_failed=True` in state. **Continue** — never sets `pipeline_stop`.
4. All extraction results (including failures) are written to `extraction_results` in state.

**Key design**: Failure is non-fatal by design. Agent 2 never stops the pipeline. A failed extraction reduces confidence but the remaining agents proceed with whatever data is available. This implements the TC011 graceful degradation requirement.

### 3.3 Agent 3: Cross-Validation

**File**: `backend/agents/cross_validation.py`

**Purpose**: Ensure documents are internally consistent and all belong to the same patient.

**Logic flow**:
1. Extract patient names from all documents that have them.
2. Compare all names pairwise using `_names_match()` — case-insensitive, allows substring inclusion (e.g. "Rajesh Kumar" matches "Mr Rajesh Kumar"), but catches clearly different names (TC003: "Rajesh Kumar" vs "Arjun Mehta").
3. If patient names conflict → fail with exact names and document types. Sets `pipeline_stop=True`.
4. If member name doesn't match document names → advisory flag only, continues pipeline, reduces confidence by 0.10.
5. Date and amount mismatches are advisory — recorded but never stop the pipeline.

**Key design**: Only patient name mismatch across documents is a hard failure (fraud risk). Other inconsistencies are recorded as advisories that reduce confidence and inform the final decision.

### 3.4 Agent 4: Policy Evaluation

**File**: `backend/agents/policy_evaluation.py`

**Purpose**: Apply every insurance policy rule deterministically. Zero LLM calls.

**10 ordered checks**:
1. **Member eligibility** — member_id exists in `policy_terms.json`
2. **Submission deadline** — treatment date ≤ 30 days before submission date
3. **Minimum amount** — claimed amount ≥ ₹500
4. **Waiting period** — fuzzy-match diagnosis against condition keyword map; check join_date against condition-specific waiting days (e.g. diabetes: 90 days, hernia: 365 days)
5. **Exclusion check** — match diagnosis against general exclusions list (e.g. "Obesity and weight loss programs"); match line items against category-specific exclusions (e.g. dental: "Teeth Whitening")
6. **Pre-authorization** — for DIAGNOSTIC claims: if MRI/CT/PET detected in any document field AND amount > ₹10,000, reject with instructions to obtain pre-auth
7. **Per-claim limit** — claimed ≤ ₹5,000 per consultation claim
8. **Sub-category limit** — claimed ≤ category sub-limit (e.g. consultation: ₹5,000, dental: ₹10,000)
9. **Annual OPD limit** — claimed + YTD ≤ ₹50,000
10. **Financial calculation** — network discount first (`hospital_name` in `network_hospitals` list → 20% for consultation), then co-pay on discounted amount (10% for consultation), cap to sub-limit

**Financial calculation order** (critical — tested by TC010):
```
Eligible amount → × (1 - network_discount%) → × (1 - copay%) → min(result, sub_limit)
₹4,500 × 0.80 = ₹3,600 → × 0.90 = ₹3,240
```

### 3.5 Agent 5: Fraud Detection

**File**: `backend/agents/fraud_detection.py`

**Purpose**: Identify suspicious claim patterns using rule-based scoring against `claims_history`.

**Four signals** (all read from `policy_terms.json → fraud_thresholds`):
1. **Same-day frequency**: claims on the same `treatment_date` ≥ 2 → `MULTIPLE_SAME_DAY_CLAIMS` flag, +0.50 to fraud score, severity HIGH
2. **Monthly frequency**: claims in same month ≥ 6 → +0.30, severity MEDIUM
3. **High-value**: claimed_amount > ₹25,000 → +0.20, severity MEDIUM
4. **Round amount**: amount > ₹1,000 and divisible by 1,000 → +0.05, severity LOW (weak signal)

**Routing decision**: Same-day limit violation alone → `MANUAL_REVIEW` regardless of total score. Score ≥ 0.80 → `MANUAL_REVIEW`. Otherwise → `CLEAR`.

**Key design**: The system routes to MANUAL_REVIEW rather than auto-rejecting on fraud signals. Fraud is flagged for human adjudicators to assess — the system never auto-rejects based on pattern alone.

### 3.6 Agent 6: Decision Aggregation

**File**: `backend/agents/decision_aggregation.py`

**Purpose**: Combine all agent results into the final decision with a confidence score and full trace.

**Priority order** (highest priority wins):
1. Document verification failed → `status=stopped_early`, `error_message` surfaced
2. Cross-validation failed → `status=stopped_early`, `error_message` surfaced
3. Fraud result is `MANUAL_REVIEW` → decision = `MANUAL_REVIEW`, confidence reduced by 0.25
4. Policy result drives decision (`APPROVED`/`PARTIAL`/`REJECTED`)

**Confidence modifiers**:
- `_component_failed` (TC011): −0.20
- `!cross_result.amount_match`: −0.05
- `!cross_result.date_match`: −0.05
- `!cross_result.member_name_match`: −0.10
- Fraud routing: −0.25
- Clear policy rejection (exclusion/waiting period/limit): override to 0.95

**Minimum confidence floor**: 0.10 — no decision ever reports 0% confidence.

### 3.7 LangGraph Orchestrator

**File**: `backend/orchestrator/pipeline.py`

**Graph topology**:
```
doc_verification →(stop)→ decision_aggregation → END
doc_verification →(continue)→ doc_extraction → cross_validation
cross_validation →(stop)→ decision_aggregation → END
cross_validation →(continue)→ policy_evaluation → fraud_detection → decision_aggregation → END
```

**State**: `ClaimState = Dict[str, Any]` with all agent results, trace entries, internal flags, and injected services.

**Timing**: Every node is wrapped in `_timed_node()` which records `started_at`, `completed_at`, and `duration_ms` for the trace.

**Services injected into state**: `policy_loader` and `llm_service` are injected at pipeline initialization so agents don't use globals. This makes agents independently testable.

---

## 4. Data Flow

A complete claim submission from frontend to response:

1. **Frontend** sends `ClaimSubmission` JSON: `member_id`, `policy_id`, `claim_category`, `treatment_date`, `claimed_amount`, `hospital_name`, `documents` (base64 file content or pre-populated content for test scenarios).

2. **FastAPI** (`POST /api/claims/submit`) validates with Pydantic, then calls `pipeline.process(submission)`.

3. **Pipeline** generates `claim_id = CLM-{8 hex chars}`, initialises `ClaimState` with all submission fields plus injected `policy_loader` and `llm_service`, records `pipeline_start` timestamp.

4. **Agent 1** classifies documents (GPT-4o or pre-set `actual_type`), checks quality and required types. Either passes or sets `pipeline_stop=True`.

5. **Agent 2** extracts structured data from each document (GPT-4o or pre-populated `content`). Never stops pipeline.

6. **Agent 3** cross-validates patient name consistency. Either passes (with advisory mismatches recorded) or sets `pipeline_stop=True`.

7. **Agent 4** runs 10 policy checks deterministically. Writes `PolicyEvalResult` to state.

8. **Agent 5** analyses `claims_history` for fraud patterns. Writes `FraudResult` with score and recommendation.

9. **Agent 6** reads all agent results, applies priority logic, calculates confidence, assembles `ClaimDecision`.

10. **Pipeline** builds `DecisionTrace` from all `_trace_entries`, calculates `total_duration_ms`, constructs and returns `ClaimResponse`.

11. **FastAPI** stores result in `claims_store` dict (in-memory), returns response.

12. **Frontend** redirects to `/claims/{claim_id}` which displays the decision and renders the full interactive trace accordion.

---

## 5. Failure Handling

### LLM API Failures (timeout, rate limit, API error)
The `LLMService` retries up to `LLM_MAX_RETRIES=2` times with exponential backoff. If all retries fail, the agent logs the error, records it in the `DocumentExtractionResult.error` field, marks `_component_failed=True`, and continues. The confidence score is reduced by 0.20 in Agent 6.

### Pydantic Validation Failures
Malformed `ClaimSubmission` payloads (missing required fields, negative amounts) are rejected by FastAPI with HTTP 422 before the pipeline starts. No agent code is called.

### Individual Agent Exception
Each agent is wrapped in `_timed_node()`. An unhandled exception sets `pipeline_stop=True` and records the error string in the trace entry's `errors` list. The pipeline then skips to Agent 6, which produces a `MANUAL_REVIEW` decision.

### Component Failure (TC011)
`simulate_component_failure=True` triggers a deliberate extraction failure on the first document. The pipeline continues with the remaining extracted data. Agent 6 detects `_component_failed=True`, reduces confidence by 0.20, and adds a manual review recommendation. The system never crashes — it produces a decision with reduced confidence and full disclosure of the failure.

### Document Problems (TC001–TC003)
Agent 1 or Agent 3 sets `pipeline_stop=True`. LangGraph routes directly to Agent 6. No extraction or policy evaluation is attempted. The response has `status="stopped_early"` and `error_message` contains the specific, actionable explanation.

---

## 6. Observability & Traceability

Every agent produces a `TraceEntry`:

```python
class TraceEntry(BaseModel):
    agent_name: str
    status: str           # "success" | "failed" | "skipped"
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    details: Dict[str, str]
    errors: List[str]
    summary: Dict[str, Any]   # agent-specific structured summary
```

The `summary` field contains the full serialised output of each agent (e.g. `DocVerificationResult`, `PolicyEvalResult`, `FraudResult`). The frontend renders this as an interactive accordion with type-specific panels:

- **Document Verification panel**: classified documents table, missing types, quality issues
- **Extraction panel**: per-document extracted fields with confidence scores
- **Cross-Validation panel**: checkmarks for name/date/amount/member consistency
- **Policy panel**: all 10 checks pass/fail, financial breakdown with each step
- **Fraud panel**: score bar, same-day/monthly/high-value stats, flags list
- **Decision panel**: final verdict, confidence bar, reasons, recommendations

Any ops team member can open a claim and see precisely why it was approved or rejected, which documents were read, what policy rules were applied, and what the financial calculation looked like step by step.

---

## 7. Scalability — Path to 10× Load

Current system handles ~75K claims/year (TechCorp: 500 employees, average ~12 OPD claims/employee/year). At 10× (750K claims/year ≈ 85 claims/hour peak):

| Current Limitation | Solution at 10× |
|---|---|
| In-memory `claims_store` — lost on restart | PostgreSQL with proper indexing on `claim_id`, `member_id`, `status` |
| Synchronous request/response — client waits for full pipeline | Async task queue (Celery + Redis or AWS SQS) with webhook callback. Return `claim_id` immediately, poll or subscribe for result. |
| Single-instance backend | Horizontal scaling behind a load balancer. Pipeline is stateless — each request is self-contained. |
| GPT-4o for every document | OpenAI Batch API for non-urgent bulk processing (50% cost reduction). Lightweight classifier (CLIP or fine-tuned ViT) for document type classification; GPT-4o only for extraction. |
| Policy loader re-reads JSON per startup | Redis cache for policy terms. Policy changes infrequently — a 1-hour TTL is acceptable. |
| Sequential agent execution | Agents 4 and 5 (Policy + Fraud) are independent after extraction and can run concurrently with `asyncio.gather()`. |
| No monitoring | Prometheus metrics (per-agent latency, pipeline duration, error rates, decision distribution). Grafana dashboards. Alert on p95 latency > 10s or error rate > 1%. |
| No document storage | S3/GCS with signed URLs. Store document references, not base64 blobs in the database. |

---

## 8. Current Limitations

- **In-memory storage**: All processed claims are lost when the backend restarts. There is no persistence layer.
- **No authentication**: Any request to `POST /api/claims/submit` is accepted. There is no member portal login or ops team auth.
- **No rate limiting**: The API can be called without restriction.
- **No document persistence**: Documents are processed and discarded. There is no audit trail of the actual images.
- **Fraud detection is frequency-only**: The fraud agent checks claim counts, amounts, and round numbers. It does not check content-based fraud (e.g. duplicate document images, forged letterheads).
- **No claim amendment workflow**: Submitted claims cannot be updated or appealed through the system.
- **Single-region deployment**: No geographic redundancy.
- **No async processing**: The frontend waits synchronously for the pipeline to complete (typically 2–8 seconds for LLM calls, <100ms for test cases).

---

## 9. What I Would Change With More Time

- **Real-time pipeline progress via SSE**: Stream trace entries to the frontend as each agent completes, rather than waiting for the full response. Users would see "Verifying documents... done. Extracting data... done." as it happens.
- **PostgreSQL persistence**: Full claim history, member claim ledger, audit log, claim amendment support.
- **Member authentication**: JWT-based member login. Members see only their own claims. Ops team sees all claims with manual review queue.
- **Richer fraud detection**: Vector similarity on extracted document text to catch duplicate bills. ML model trained on historical claim patterns to flag anomalies beyond simple frequency counting.
- **A/B testing for extraction prompts**: Different prompt versions for different document quality levels. Track extraction accuracy per prompt variant.
- **Integration tests with real document images**: The current test suite uses pre-populated structured data. A test set of actual scanned Indian medical documents would validate the full GPT-4o path.
- **CI/CD pipeline**: GitHub Actions running `pytest` and the eval suite on every PR. Deploy to Railway only on green main.
- **Batch processing mode**: Accept a CSV of claims and process asynchronously, returning results via webhook. Needed for bulk reprocessing or appeals handling.
