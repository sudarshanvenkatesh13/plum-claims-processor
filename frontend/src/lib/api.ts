import type {
  ClaimSubmission,
  ClaimResponse,
  Member,
  CategoryInfo,
  EvalResponse,
  EvalSingleResult,
  TestCasesResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  submitClaim: (data: ClaimSubmission) =>
    request<ClaimResponse>("/api/claims/submit", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getClaim: (claimId: string) =>
    request<ClaimResponse>(`/api/claims/${claimId}`),

  getAllClaims: () =>
    request<Array<{
      claim_id: string;
      status: string;
      decision: string | null;
      approved_amount: number | null;
      confidence_score: number;
    }>>("/api/claims"),

  getMembers: () =>
    request<Member[]>("/api/policy/members"),

  getCategories: () =>
    request<Record<string, CategoryInfo>>("/api/policy/categories"),

  runEval: () =>
    request<EvalResponse>("/api/eval/run", { method: "POST" }),

  getTestCases: () =>
    request<TestCasesResponse>("/api/eval/test-cases"),

  runSingleEval: (caseId: string) =>
    request<EvalSingleResult>("/api/eval/run-single", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId }),
    }),

  health: () =>
    request<{ status: string }>("/health"),
};

// ── Helpers ───────────────────────────────────────────────────────────────────

export function formatINR(amount: number | null | undefined): string {
  if (amount == null) return "—";
  return `₹${amount.toLocaleString("en-IN")}`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export const DECISION_CONFIG: Record<
  string,
  { bg: string; border: string; text: string; badgeBg: string; badgeText: string; label: string }
> = {
  APPROVED: {
    bg: "bg-emerald-50",
    border: "border-emerald-500",
    text: "text-emerald-700",
    badgeBg: "bg-emerald-100",
    badgeText: "text-emerald-800",
    label: "Approved",
  },
  PARTIAL: {
    bg: "bg-amber-50",
    border: "border-amber-500",
    text: "text-amber-700",
    badgeBg: "bg-amber-100",
    badgeText: "text-amber-800",
    label: "Partially Approved",
  },
  REJECTED: {
    bg: "bg-red-50",
    border: "border-red-500",
    text: "text-red-700",
    badgeBg: "bg-red-100",
    badgeText: "text-red-800",
    label: "Rejected",
  },
  MANUAL_REVIEW: {
    bg: "bg-blue-50",
    border: "border-blue-500",
    text: "text-blue-700",
    badgeBg: "bg-blue-100",
    badgeText: "text-blue-800",
    label: "Manual Review",
  },
};

export const DOC_TYPE_LABELS: Record<string, string> = {
  PRESCRIPTION: "Prescription",
  HOSPITAL_BILL: "Hospital Bill",
  LAB_REPORT: "Lab Report",
  PHARMACY_BILL: "Pharmacy Bill",
  DENTAL_REPORT: "Dental Report",
  DIAGNOSTIC_REPORT: "Diagnostic Report",
  DISCHARGE_SUMMARY: "Discharge Summary",
  UNKNOWN: "Unknown",
};

export const CATEGORY_DOC_REQUIREMENTS: Record<
  string,
  { required: string[]; optional: string[] }
> = {
  CONSULTATION: {
    required: ["PRESCRIPTION", "HOSPITAL_BILL"],
    optional: ["LAB_REPORT", "DIAGNOSTIC_REPORT"],
  },
  DIAGNOSTIC: {
    required: ["PRESCRIPTION", "LAB_REPORT", "HOSPITAL_BILL"],
    optional: ["DISCHARGE_SUMMARY"],
  },
  PHARMACY: {
    required: ["PRESCRIPTION", "PHARMACY_BILL"],
    optional: [],
  },
  DENTAL: {
    required: ["HOSPITAL_BILL"],
    optional: ["PRESCRIPTION", "DENTAL_REPORT"],
  },
  VISION: {
    required: ["PRESCRIPTION", "HOSPITAL_BILL"],
    optional: [],
  },
  ALTERNATIVE_MEDICINE: {
    required: ["PRESCRIPTION", "HOSPITAL_BILL"],
    optional: [],
  },
};
