"use client";

import { formatINR, DOC_TYPE_LABELS, DECISION_CONFIG } from "@/lib/api";
import type {
  TraceEntry,
  DecisionTrace,
  DocVerificationSummary,
  ExtractionSummary,
  CrossValidationSummary,
  PolicyEvalSummary,
  FraudSummary,
  DecisionSummary,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";

// ── Shared helpers ────────────────────────────────────────────────────────────

export function CheckRow({ label, passed, details }: { label: string; passed: boolean; details?: string }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
      <div className={`mt-0.5 w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${passed ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-600"}`}>
        {passed ? (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>
        ) : (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {details && <p className="text-xs text-gray-500 mt-0.5">{details}</p>}
      </div>
      <span className={`text-xs font-semibold shrink-0 ${passed ? "text-emerald-600" : "text-red-600"}`}>{passed ? "Pass" : "Fail"}</span>
    </div>
  );
}

export function AgentStatusIcon({ status }: { status: string }) {
  if (status === "success")
    return <span className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center shrink-0"><svg className="w-3 h-3 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg></span>;
  if (status === "failed")
    return <span className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center shrink-0"><svg className="w-3 h-3 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></span>;
  return <span className="w-5 h-5 rounded-full bg-gray-100 flex items-center justify-center shrink-0"><svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg></span>;
}

export function DurationBadge({ ms }: { ms: number | null | undefined }) {
  if (!ms) return null;
  return <span className="text-xs text-gray-400 ml-2">{ms.toFixed(0)}ms</span>;
}

// ── Per-agent timing strip ────────────────────────────────────────────────────

const AGENT_SHORT_NAMES: Record<string, string> = {
  DocumentVerification: "Doc Verify",
  DocumentExtraction: "Extraction",
  CrossValidation: "Cross-Val",
  PolicyEvaluation: "Policy",
  FraudDetection: "Fraud",
  DecisionAggregation: "Decision",
};

export function AgentTimingRow({ timing }: { timing: Record<string, number> }) {
  const keys = Object.keys(AGENT_SHORT_NAMES);
  const present = keys.filter((k) => timing[k] != null);
  if (present.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {present.map((key) => (
        <span key={key} className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
          <span>{AGENT_SHORT_NAMES[key]}</span>
          <span className="font-semibold text-gray-800">{Math.round(timing[key])}ms</span>
        </span>
      ))}
    </div>
  );
}

// ── Agent panels ──────────────────────────────────────────────────────────────

function DocVerificationPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as DocVerificationSummary;
  if (!s || !s.status) return <p className="text-xs text-gray-400 p-3">No data available.</p>;
  return (
    <div className="p-4 space-y-3">
      {s.error_message && <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm text-orange-800">{s.error_message}</div>}
      {(s.classified_documents?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Classified Documents</p>
          <div className="space-y-1.5">
            {s.classified_documents.map((doc) => (
              <div key={doc.file_id} className="flex items-center gap-2 text-sm bg-gray-50 rounded px-3 py-1.5">
                <span className="font-medium text-gray-700 min-w-0 flex-1 truncate">{doc.file_name}</span>
                <Badge variant="outline" className="text-xs">{DOC_TYPE_LABELS[doc.detected_type] ?? doc.detected_type}</Badge>
                <Badge variant={doc.quality === "GOOD" ? "default" : "destructive"} className={`text-xs ${doc.quality === "GOOD" ? "bg-emerald-100 text-emerald-800 border-emerald-200" : ""}`}>{doc.quality}</Badge>
                <span className="text-xs text-gray-400">{Math.round(doc.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {(s.missing_documents?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1">Missing Required Documents</p>
          {s.missing_documents.map((d) => <span key={d} className="inline-block bg-red-50 text-red-700 text-xs rounded px-2 py-0.5 mr-1 mb-1">{DOC_TYPE_LABELS[d] ?? d}</span>)}
        </div>
      )}
      {(s.quality_issues?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-500 uppercase tracking-wide mb-1">Quality Issues</p>
          {s.quality_issues.map((q) => <span key={q} className="inline-block bg-amber-50 text-amber-700 text-xs rounded px-2 py-0.5 mr-1 mb-1">{q}</span>)}
        </div>
      )}
    </div>
  );
}

function ExtractionPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as ExtractionSummary;
  if (!s || s.documents_extracted == null) return <p className="text-xs text-gray-400 p-3">No extraction data.</p>;
  return (
    <div className="p-4 space-y-3">
      {s.component_failed && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2 text-sm text-amber-800">
          <svg className="w-4 h-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
          <span><strong>Component failure simulated.</strong> One document was not extracted — pipeline continued with partial data.</span>
        </div>
      )}
      {s.extractions?.map((ex) => (
        <div key={ex.file_id} className={`border rounded-lg p-3 ${ex.error ? "border-red-200 bg-red-50" : "border-gray-100 bg-gray-50"}`}>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="outline" className="text-xs">{DOC_TYPE_LABELS[ex.document_type] ?? ex.document_type}</Badge>
            <span className="text-xs text-gray-400">{ex.file_id}</span>
            <span className="ml-auto text-xs text-gray-500">{Math.round(ex.confidence * 100)}% confidence</span>
          </div>
          {ex.error ? (
            <p className="text-xs text-red-600">{ex.error}</p>
          ) : ex.extraction ? (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(ex.extraction).filter(([,v]) => v != null && v !== "" && !Array.isArray(v)).slice(0,8).map(([k,v]) => (
                <div key={k} className="flex items-start gap-1 text-xs">
                  <span className="text-gray-400 shrink-0 capitalize">{k.replace(/_/g," ")}:</span>
                  <span className="text-gray-700 font-medium truncate">{String(v)}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-gray-400">No structured data extracted.</p>}
        </div>
      ))}
    </div>
  );
}

function CrossValidationPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as CrossValidationSummary;
  if (!s || !s.status) return <p className="text-xs text-gray-400 p-3">No data available.</p>;
  return (
    <div className="p-4 space-y-2">
      {s.error_message && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800 mb-3">{s.error_message}</div>}
      <CheckRow label="Patient name consistent across documents" passed={s.patient_name_match}/>
      <CheckRow label="Treatment dates consistent" passed={s.date_match}/>
      <CheckRow label="Bill amounts match claimed amount" passed={s.amount_match}/>
      <CheckRow label="Patient name matches policy member" passed={s.member_name_match}/>
      {(s.mismatches?.length ?? 0) > 0 && (
        <div className="mt-3 space-y-2">
          {s.mismatches.map((m, i) => (
            <div key={i} className="bg-amber-50 border border-amber-100 rounded p-2 text-xs text-amber-800">
              {m.type === "patient_name_mismatch"
                ? <span><strong>{String(m.doc_a)}</strong>: &quot;{String(m.name_a)}&quot; vs <strong>{String(m.doc_b)}</strong>: &quot;{String(m.name_b)}&quot;</span>
                : m.type === "amount_mismatch"
                ? <span>Billed {formatINR(m.billed_total as number)} vs claimed {formatINR(m.claimed_amount as number)}</span>
                : <span>{JSON.stringify(m)}</span>
              }
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PolicyEvalPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as PolicyEvalSummary;
  if (!s || !s.overall_decision) return <p className="text-xs text-gray-400 p-3">No data available.</p>;
  const fin = s.financial_calculation;
  return (
    <div className="p-4 space-y-4">
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Policy Checks</p>
        <div className="bg-gray-50 rounded-lg overflow-hidden">
          <CheckRow label="Member eligibility" passed={s.member_eligible?.passed ?? true} details={s.member_eligible?.details}/>
          <CheckRow label="Within submission deadline" passed={s.within_submission_deadline?.passed ?? true} details={s.within_submission_deadline?.details}/>
          <CheckRow label="Minimum claim amount" passed={s.minimum_amount_met ?? true}/>
          <CheckRow
            label={`Waiting period${s.waiting_period_check?.condition ? ` (${s.waiting_period_check.condition.replace(/_/g," ")})` : ""}`}
            passed={s.waiting_period_check?.passed ?? true}
            details={s.waiting_period_check && !s.waiting_period_check.passed
              ? `${s.waiting_period_check.actual_days} days elapsed, ${s.waiting_period_check.required_days} required. Eligible from ${s.waiting_period_check.eligible_date ?? "—"}`
              : undefined}
          />
          <CheckRow label="Exclusion check" passed={s.exclusion_check?.passed ?? true}
            details={s.exclusion_check?.excluded_items?.length ? `Excluded: ${s.exclusion_check.excluded_items.map((e) => e.item).join(", ")}` : undefined}/>
          <CheckRow label="Pre-authorization" passed={s.pre_auth_check?.passed ?? true} details={s.pre_auth_check?.details}/>
          <CheckRow label={`Per-claim limit (${formatINR(s.limit_checks?.per_claim?.limit ?? 0)})`}
            passed={s.limit_checks?.per_claim?.passed ?? true}
            details={!s.limit_checks?.per_claim?.passed ? `Claimed ${formatINR(s.limit_checks.per_claim.claimed)}` : undefined}/>
          <CheckRow label="Sub-category limit" passed={s.limit_checks?.sub_limit?.passed ?? true}/>
          <CheckRow label={`Annual OPD limit (${formatINR(s.limit_checks?.annual?.limit ?? 0)})`}
            passed={s.limit_checks?.annual?.passed ?? true}
            details={`YTD: ${formatINR(s.limit_checks?.annual?.ytd ?? 0)}`}/>
        </div>
      </div>
      {fin?.breakdown?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Financial Calculation</p>
          <div className="bg-teal-50 border border-teal-100 rounded-lg p-3 space-y-1.5">
            {fin.breakdown.map((item, i) => (
              <div key={i} className={`flex items-center justify-between text-sm ${i === fin.breakdown.length - 1 ? "font-semibold text-teal-900 border-t border-teal-200 pt-1.5 mt-1.5" : "text-gray-700"}`}>
                <span>{item.label}</span>
                <span className={item.amount < 0 ? "text-red-600" : "text-gray-900"}>
                  {item.amount < 0 ? `−${formatINR(Math.abs(item.amount))}` : formatINR(item.amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {(s.line_item_results?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Line Item Results</p>
          <div className="space-y-1">
            {s.line_item_results.map((li, i) => (
              <div key={i} className="flex items-center gap-2 text-sm bg-gray-50 rounded px-3 py-1.5">
                <span className="flex-1 text-gray-700">{li.description}</span>
                <span className="text-gray-600 tabular-nums">{formatINR(li.amount)}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${li.status === "approved" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{li.status}</span>
                {li.reason && <span className="text-xs text-gray-400">{li.reason}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
      {(s.rejection_reasons?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1">Rejection Reasons</p>
          {s.rejection_reasons.map((r, i) => <p key={i} className="text-sm text-gray-700 bg-red-50 border border-red-100 rounded p-2 mb-1">{r}</p>)}
        </div>
      )}
    </div>
  );
}

function FraudPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as FraudSummary;
  if (!s || s.fraud_score == null) return <p className="text-xs text-gray-400 p-3">No data available.</p>;
  const scoreColor = s.fraud_score < 0.3 ? "text-emerald-600" : s.fraud_score < 0.6 ? "text-amber-600" : "text-red-600";
  const barColor = s.fraud_score < 0.3 ? "bg-emerald-500" : s.fraud_score < 0.6 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="p-4 space-y-4">
      <div className="bg-gray-50 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Fraud Risk Score</span>
          <span className={`text-lg font-bold ${scoreColor}`}>{Math.round(s.fraud_score * 100)}%</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-full ${barColor} rounded-full`} style={{ width: `${s.fraud_score * 100}%` }}/>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center bg-gray-50 rounded-lg p-3"><p className="text-xl font-bold text-gray-900">{s.same_day_count}</p><p className="text-xs text-gray-500">Same-day claims</p></div>
        <div className="text-center bg-gray-50 rounded-lg p-3"><p className="text-xl font-bold text-gray-900">{s.monthly_count}</p><p className="text-xs text-gray-500">This month</p></div>
        <div className={`text-center rounded-lg p-3 ${s.is_high_value ? "bg-amber-50" : "bg-gray-50"}`}>
          <p className={`text-xl font-bold ${s.is_high_value ? "text-amber-600" : "text-gray-900"}`}>{s.is_high_value ? "Yes" : "No"}</p>
          <p className="text-xs text-gray-500">High-value</p>
        </div>
      </div>
      <div className={`rounded-lg p-3 border text-sm font-medium flex items-center gap-2 ${s.recommendation === "CLEAR" ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-amber-50 border-amber-200 text-amber-700"}`}>
        {s.recommendation === "CLEAR"
          ? <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          : <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
        }
        Recommendation: {s.recommendation}
      </div>
      {(s.flags?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Flags Detected</p>
          {s.flags.map((flag, i) => (
            <div key={i} className="bg-red-50 border border-red-100 rounded p-2.5 mb-2">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-semibold text-red-700">{flag.flag_type.replace(/_/g," ")}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${flag.severity === "high" ? "bg-red-100 text-red-700" : flag.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"}`}>{flag.severity}</span>
              </div>
              <p className="text-xs text-gray-600">{flag.details}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DecisionPanel({ entry }: { entry: TraceEntry }) {
  const s = entry.summary as unknown as DecisionSummary;
  if (!s || !s.decision) return <p className="text-xs text-gray-400 p-3">No data available.</p>;
  const cfg = DECISION_CONFIG[s.decision];
  return (
    <div className="p-4 space-y-3">
      <div className={`rounded-lg p-3 border ${cfg?.border ?? "border-gray-200"} ${cfg?.bg ?? "bg-gray-50"}`}>
        <div className="flex items-center justify-between">
          <span className={`font-semibold text-sm ${cfg?.text ?? "text-gray-700"}`}>{cfg?.label ?? s.decision}</span>
          <span className="font-bold text-gray-900">{s.approved_amount ? formatINR(s.approved_amount) : "—"}</span>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs text-gray-500">Confidence:</span>
          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-teal-500 rounded-full" style={{ width: `${s.confidence_score * 100}%` }}/></div>
          <span className="text-xs font-medium text-gray-700">{Math.round(s.confidence_score * 100)}%</span>
        </div>
      </div>
      {(s.reasons?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Reasons</p>
          {s.reasons.map((r, i) => <p key={i} className="text-sm text-gray-700 flex items-start gap-2 mb-1"><span className="text-gray-400 shrink-0">·</span>{r}</p>)}
        </div>
      )}
      {(s.recommendations?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-teal-600 uppercase tracking-wide mb-1.5">Recommendations</p>
          {s.recommendations.map((r, i) => <p key={i} className="text-sm text-teal-700 bg-teal-50 rounded px-2.5 py-1.5 mb-1">{r}</p>)}
        </div>
      )}
      {(s.errors?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1.5">Errors</p>
          {s.errors.map((r, i) => <p key={i} className="text-sm text-red-600 bg-red-50 rounded px-2.5 py-1.5 mb-1">{r}</p>)}
        </div>
      )}
    </div>
  );
}

// ── Trace accordion config ────────────────────────────────────────────────────

export const AGENT_META: Record<string, { title: string; subtitle: (e: TraceEntry) => string }> = {
  DocumentVerification: {
    title: "Document Verification",
    subtitle: (e) => {
      const s = e.summary as unknown as DocVerificationSummary;
      if (!s?.status) return e.status === "failed" ? "Agent failed" : "Completed";
      return s.status === "passed"
        ? `${s.classified_documents?.length ?? 0} documents verified`
        : `Failed — ${s.missing_documents?.length ? `missing: ${s.missing_documents.join(", ")}` : s.error_message ?? "check required"}`;
    },
  },
  DocumentExtraction: {
    title: "Information Extraction",
    subtitle: (e) => {
      const s = e.summary as unknown as ExtractionSummary;
      if (!s) return "Completed";
      return s.component_failed ? "Partial — component failure on 1 document" : `${s.documents_extracted} documents extracted`;
    },
  },
  CrossValidation: {
    title: "Cross-Validation",
    subtitle: (e) => {
      const s = e.summary as unknown as CrossValidationSummary;
      if (!s?.status) return "Completed";
      return s.status === "passed" ? "All documents consistent" : `Failed — ${s.error_message ?? "inconsistency detected"}`;
    },
  },
  PolicyEvaluation: {
    title: "Policy Evaluation",
    subtitle: (e) => {
      const s = e.summary as unknown as PolicyEvalSummary;
      if (!s?.overall_decision) return "Completed";
      return `${s.overall_decision} — ${s.rejection_reasons?.length ? s.rejection_reasons[0].slice(0, 80) : "all checks passed"}`;
    },
  },
  FraudDetection: {
    title: "Fraud Detection",
    subtitle: (e) => {
      const s = e.summary as unknown as FraudSummary;
      if (!s) return "Completed";
      return `Score ${Math.round((s.fraud_score ?? 0) * 100)}% · ${s.recommendation ?? "CLEAR"} · ${s.flags?.length ?? 0} flag(s)`;
    },
  },
  DecisionAggregation: {
    title: "Final Decision",
    subtitle: (e) => {
      const s = e.summary as unknown as DecisionSummary;
      if (!s?.decision) return "Completed";
      return `${s.decision} · ${Math.round((s.confidence_score ?? 0) * 100)}% confidence`;
    },
  },
};

function AgentPanel({ entry }: { entry: TraceEntry }) {
  switch (entry.agent_name) {
    case "DocumentVerification": return <DocVerificationPanel entry={entry}/>;
    case "DocumentExtraction":   return <ExtractionPanel entry={entry}/>;
    case "CrossValidation":      return <CrossValidationPanel entry={entry}/>;
    case "PolicyEvaluation":     return <PolicyEvalPanel entry={entry}/>;
    case "FraudDetection":       return <FraudPanel entry={entry}/>;
    case "DecisionAggregation":  return <DecisionPanel entry={entry}/>;
    default: return <div className="p-4 text-xs text-gray-500 font-mono whitespace-pre-wrap bg-gray-50">{JSON.stringify(entry.summary, null, 2)}</div>;
  }
}

// ── Main TraceViewer component ────────────────────────────────────────────────

export function TraceViewer({ trace, defaultExpanded = true }: { trace: DecisionTrace; defaultExpanded?: boolean }) {
  return (
    <Accordion multiple defaultValue={defaultExpanded ? trace.entries.map((e) => e.agent_name) : []}>
      {trace.entries.map((entry) => {
        const meta = AGENT_META[entry.agent_name];
        return (
          <AccordionItem key={entry.agent_name} value={entry.agent_name}>
            <AccordionTrigger className="px-1 py-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <AgentStatusIcon status={entry.status}/>
                <div className="min-w-0">
                  <span className="font-semibold text-sm text-gray-900">{meta?.title ?? entry.agent_name}</span>
                  {meta && <span className="text-xs text-gray-400 ml-2 truncate hidden sm:inline">{meta.subtitle(entry)}</span>}
                </div>
                <DurationBadge ms={entry.duration_ms}/>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="border border-gray-100 rounded-lg overflow-hidden mt-1 mb-2">
                {(entry.errors?.length ?? 0) > 0 && (
                  <div className="bg-red-50 px-4 py-2 border-b border-red-100">
                    {entry.errors.map((e, i) => <p key={i} className="text-xs text-red-600">⚠ {e}</p>)}
                  </div>
                )}
                <AgentPanel entry={entry}/>
              </div>
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
