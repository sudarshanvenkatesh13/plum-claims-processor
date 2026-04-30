// ── Enums ────────────────────────────────────────────────────────────────────

export type ClaimCategory =
  | "CONSULTATION"
  | "DIAGNOSTIC"
  | "PHARMACY"
  | "DENTAL"
  | "VISION"
  | "ALTERNATIVE_MEDICINE";

export type Decision = "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW";

export type DocumentType =
  | "PRESCRIPTION"
  | "HOSPITAL_BILL"
  | "LAB_REPORT"
  | "PHARMACY_BILL"
  | "DENTAL_REPORT"
  | "DIAGNOSTIC_REPORT"
  | "DISCHARGE_SUMMARY"
  | "UNKNOWN";

export type DocumentQuality = "GOOD" | "POOR" | "UNREADABLE";

// ── Submission models ─────────────────────────────────────────────────────────

export interface UploadedDocument {
  file_id: string;
  file_name: string;
  file_content: string; // base64 or data-URI
  actual_type?: string | null;
  quality?: string | null;
  content?: Record<string, unknown> | null;
}

export interface PriorClaim {
  claim_id: string;
  date: string; // ISO date string
  amount: number;
  provider: string;
}

export interface ClaimSubmission {
  member_id: string;
  policy_id: string;
  claim_category: ClaimCategory;
  treatment_date: string;
  claimed_amount: number;
  hospital_name?: string | null;
  diagnosis?: string | null;
  documents: UploadedDocument[];
  claims_history?: PriorClaim[] | null;
  ytd_claims_amount?: number;
  simulate_component_failure?: boolean;
}

// ── Response models ───────────────────────────────────────────────────────────

export interface LineItemResult {
  description: string;
  amount: number;
  status: "approved" | "rejected";
  reason?: string | null;
}

export interface FinancialBreakdownItem {
  label: string;
  amount: number;
}

export interface TraceEntry {
  agent_name: string;
  status: "success" | "failed" | "skipped";
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  details: Record<string, string>;
  errors: string[];
  summary: Record<string, unknown>;
}

export interface DecisionTrace {
  entries: TraceEntry[];
  total_duration_ms: number | null;
  pipeline_status: string;
}

export interface ClaimResponse {
  claim_id: string;
  status: "completed" | "stopped_early";
  decision: Decision | null;
  approved_amount: number | null;
  confidence_score: number;
  reasons: string[];
  trace: DecisionTrace | null;
  errors: string[];
  recommendations: string[];
  error_message: string | null;
}

// ── Policy models ─────────────────────────────────────────────────────────────

export interface Member {
  member_id: string;
  name: string;
  age?: number | null;
  date_of_birth?: string | null;
  gender?: string | null;
  relationship?: string | null;
  join_date?: string | null;
}

export interface CategoryInfo {
  config: {
    sub_limit?: number;
    copay_percent?: number;
    network_discount_percent?: number;
    covered?: boolean;
  };
  document_requirements: {
    required: string[];
    optional: string[];
  };
}

// ── Structured trace summaries (per-agent) ───────────────────────────────────

export interface ClassifiedDocument {
  file_id: string;
  file_name: string;
  detected_type: DocumentType;
  quality: DocumentQuality;
  confidence: number;
}

export interface DocVerificationSummary {
  status: "passed" | "failed";
  classified_documents: ClassifiedDocument[];
  missing_documents: string[];
  quality_issues: string[];
  error_message: string | null;
}

export interface ExtractionItem {
  file_id: string;
  document_type: DocumentType;
  confidence: number;
  error: string | null;
  extraction: Record<string, unknown> | null;
}

export interface ExtractionSummary {
  documents_extracted: number;
  component_failed: boolean;
  extractions: ExtractionItem[];
}

export interface CrossValidationSummary {
  status: "passed" | "failed";
  patient_name_match: boolean;
  date_match: boolean;
  amount_match: boolean;
  member_name_match: boolean;
  mismatches: Array<Record<string, unknown>>;
  error_message: string | null;
}

export interface WaitingPeriodCheck {
  passed: boolean;
  condition: string | null;
  required_days: number;
  actual_days: number;
  eligible_date: string | null;
}

export interface FinancialCalc {
  claimed_amount: number;
  network_discount: number;
  after_discount: number;
  copay_amount: number;
  after_copay: number;
  sub_limit_cap: number;
  approved_amount: number;
  breakdown: FinancialBreakdownItem[];
}

export interface PolicyEvalSummary {
  overall_decision: Decision;
  rejection_reasons: string[];
  member_eligible: { passed: boolean; details: string };
  within_submission_deadline: { passed: boolean; details: string };
  minimum_amount_met: boolean;
  waiting_period_check: WaitingPeriodCheck;
  exclusion_check: { passed: boolean; excluded_items: Array<Record<string, string>> };
  pre_auth_check: { passed: boolean; details: string };
  limit_checks: {
    per_claim: { passed: boolean; limit: number; claimed: number };
    sub_limit: { passed: boolean; limit: number; amount: number };
    annual: { passed: boolean; limit: number; ytd: number };
  };
  financial_calculation: FinancialCalc;
  line_item_results: LineItemResult[];
}

export interface FraudFlag {
  flag_type: string;
  details: string;
  severity: "low" | "medium" | "high";
}

export interface FraudSummary {
  fraud_score: number;
  flags: FraudFlag[];
  same_day_count: number;
  monthly_count: number;
  is_high_value: boolean;
  recommendation: string;
}

export interface DecisionSummary {
  decision: Decision;
  approved_amount: number;
  confidence_score: number;
  reasons: string[];
  recommendations: string[];
  errors: string[];
}

// ── Eval ──────────────────────────────────────────────────────────────────────

export interface EvalResult {
  case_id: string;
  case_name: string;
  expected_decision: string | null;
  actual_decision: string | null;
  expected_amount: number | null;
  actual_amount: number | null;
  actual_status: string;
  confidence_score: number;
  passed: boolean;
  reason: string;
  error_message: string | null;
  reasons: string[];
  duration_ms: number;
}

export interface EvalSingleResult extends EvalResult {
  trace: DecisionTrace | null;
  agent_timing: Record<string, number>;
  // full ClaimResponse fields also included
  claim_id?: string;
  errors?: string[];
  recommendations?: string[];
}

export interface EvalResponse {
  total: number;
  passed: number;
  failed: number;
  results: EvalResult[];
}

// ── Test Cases ────────────────────────────────────────────────────────────────

export interface TestCaseDocument {
  file_id: string;
  file_name?: string | null;
  actual_type?: string | null;
  quality?: string | null;
  content?: Record<string, unknown> | null;
  patient_name_on_doc?: string | null;
}

export interface TestCaseInput {
  member_id: string;
  policy_id: string;
  claim_category: ClaimCategory;
  treatment_date: string;
  claimed_amount: number;
  hospital_name?: string | null;
  diagnosis?: string | null;
  ytd_claims_amount?: number | null;
  simulate_component_failure?: boolean | null;
  claims_history?: Array<{
    claim_id: string;
    date: string;
    amount: number;
    provider: string;
  }> | null;
  documents: TestCaseDocument[];
}

export interface TestCase {
  case_id: string;
  case_name: string;
  description: string;
  input: TestCaseInput;
  expected: {
    decision: string | null;
    approved_amount?: number | null;
    notes?: string;
    rejection_reasons?: string[];
    system_must?: string[];
    confidence_score?: string;
  };
}

export interface TestCasesResponse {
  version: string;
  description?: string;
  test_cases: TestCase[];
  notes?: string[];
}
