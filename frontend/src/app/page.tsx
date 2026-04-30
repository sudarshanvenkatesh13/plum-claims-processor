"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, formatINR, DOC_TYPE_LABELS, CATEGORY_DOC_REQUIREMENTS } from "@/lib/api";
import type { Member, ClaimCategory, UploadedDocument, PriorClaim, TestCase } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

// ── Test scenario config ──────────────────────────────────────────────────────

const TC_FRIENDLY_NAMES: Record<string, string> = {
  TC001: "Wrong Documents (Consultation - missing hospital bill)",
  TC002: "Unreadable Document (Pharmacy - blurry bill)",
  TC003: "Patient Name Mismatch (Consultation - different names on docs)",
  TC004: "Clean Approval (Consultation - standard claim)",
  TC005: "Waiting Period Rejection (Diagnostic - diabetes within 90 days)",
  TC006: "Partial Approval (Dental - covered + excluded procedures)",
  TC007: "Pre-Auth Missing (Diagnostic - MRI without authorization)",
  TC008: "Per-Claim Limit Exceeded (Consultation - over 5000 limit)",
  TC009: "Fraud Detection (Consultation - multiple same-day claims)",
  TC010: "Network Hospital Discount (Consultation - Apollo Hospitals)",
  TC011: "Component Failure (Consultation - graceful degradation test)",
  TC012: "Excluded Condition (Consultation - obesity/bariatric)",
};

const SCENARIO_DESCRIPTIONS: Record<string, string> = {
  TC001: "Verifies system catches missing required documents",
  TC002: "Verifies system detects unreadable documents",
  TC003: "Verifies system catches patient name mismatches across documents",
  TC004: "Standard consultation claim with 10% co-pay",
  TC005: "Diabetes treatment within 90-day waiting period",
  TC006: "Dental claim with mix of covered and excluded procedures",
  TC007: "MRI scan over ₹10,000 without pre-authorization",
  TC008: "Claim amount exceeds per-claim limit of ₹5,000",
  TC009: "Multiple same-day claims triggering fraud detection",
  TC010: "Network hospital discount applied before co-pay",
  TC011: "System handles component failure gracefully",
  TC012: "Treatment for excluded condition (obesity)",
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface DocSlot {
  id: string;
  docType: string;
  required: boolean;
  file: File | null;
  base64: string;
  preview: string | null;
}

interface ScenarioDoc {
  file_id: string;
  docType: string;
  quality: string | null;
  content: Record<string, unknown> | null;
  fileName: string;
}

interface PriorClaimInput {
  claim_id: string;
  date: string;
  amount: string;
  provider: string;
}

// ── Loading overlay ───────────────────────────────────────────────────────────

const STEPS = [
  "Verifying documents…",
  "Extracting information…",
  "Evaluating policy rules…",
  "Checking fraud patterns…",
  "Making final decision…",
];

function LoadingOverlay({ step }: { step: number }) {
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-sm mx-4">
        <div className="flex flex-col items-center gap-5">
          <div className="w-12 h-12 rounded-full border-4 border-teal-600 border-t-transparent animate-spin" />
          <div className="text-center">
            <p className="font-semibold text-gray-900 mb-1">Processing Claim</p>
            <p className="text-sm text-gray-500">{STEPS[Math.min(step, STEPS.length - 1)]}</p>
          </div>
          <div className="w-full space-y-1.5">
            {STEPS.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                  i < step ? "bg-teal-600" : i === step ? "bg-teal-200 border-2 border-teal-600" : "bg-gray-100"
                }`}>
                  {i < step && (
                    <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <span className={i <= step ? "text-gray-700" : "text-gray-400"}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Test doc card ─────────────────────────────────────────────────────────────

function TestDocCard({ doc }: { doc: ScenarioDoc }) {
  const qualityColor =
    doc.quality === "GOOD" ? "bg-emerald-100 text-emerald-700" :
    doc.quality === "UNREADABLE" ? "bg-red-100 text-red-700" :
    doc.quality === "POOR" ? "bg-amber-100 text-amber-700" : "";

  const contentPreview = doc.content
    ? Object.entries(doc.content)
        .filter(([, v]) => v != null && typeof v === "string")
        .slice(0, 2)
        .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
        .join(" · ")
    : null;

  return (
    <div className="flex items-start gap-3 bg-violet-50 border border-violet-200 rounded-lg p-3">
      <div className="w-9 h-9 bg-violet-100 rounded flex items-center justify-center shrink-0 mt-0.5">
        <svg className="w-5 h-5 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-900">{DOC_TYPE_LABELS[doc.docType] ?? doc.docType}</span>
          {doc.quality && (
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${qualityColor}`}>{doc.quality}</span>
          )}
        </div>
        <p className="text-xs text-violet-600 mt-0.5">Test document — pre-populated data</p>
        {contentPreview && <p className="text-xs text-gray-400 mt-0.5 truncate">{contentPreview}</p>}
      </div>
    </div>
  );
}

// ── Doc upload slot ───────────────────────────────────────────────────────────

function DocUploadSlot({ slot, onChange }: { slot: DocSlot; onChange: (updated: DocSlot) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
    });
    const preview = file.type.startsWith("image/") ? base64 : null;
    onChange({ ...slot, file, base64, preview });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <Label className="text-sm font-medium text-gray-700">{DOC_TYPE_LABELS[slot.docType] ?? slot.docType}</Label>
        {slot.required ? (
          <Badge variant="destructive" className="text-[10px] px-1.5 py-0">Required</Badge>
        ) : (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">Optional</Badge>
        )}
      </div>

      {slot.file ? (
        <div className="border border-teal-200 bg-teal-50 rounded-lg p-3 flex items-center gap-3">
          {slot.preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={slot.preview} alt="preview" className="w-12 h-12 object-cover rounded border border-gray-200" />
          ) : (
            <div className="w-12 h-12 bg-teal-100 rounded flex items-center justify-center">
              <svg className="w-6 h-6 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{slot.file.name}</p>
            <p className="text-xs text-gray-500">{(slot.file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button onClick={() => onChange({ ...slot, file: null, base64: "", preview: null })}
            className="text-gray-400 hover:text-red-500 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ) : (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="border-2 border-dashed border-gray-200 rounded-lg p-4 flex flex-col items-center gap-1.5 cursor-pointer hover:border-teal-400 hover:bg-teal-50/30 transition-colors"
        >
          <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
          <span className="text-xs text-gray-500">Click or drag file here</span>
          <span className="text-xs text-gray-400">JPG, PNG, PDF</span>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*,.pdf"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SubmitClaimPage() {
  const router = useRouter();

  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [testCases, setTestCases] = useState<TestCase[]>([]);

  // Form state
  const [memberId, setMemberId] = useState("");
  const [category, setCategory] = useState<ClaimCategory | "">("");
  const [treatmentDate, setTreatmentDate] = useState("");
  const [claimedAmount, setClaimedAmount] = useState("");
  const [hospitalName, setHospitalName] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [ytdAmount, setYtdAmount] = useState("0");
  const [simFailure, setSimFailure] = useState(false);
  const [priorClaims, setPriorClaims] = useState<PriorClaimInput[]>([]);
  const [docSlots, setDocSlots] = useState<DocSlot[]>([]);

  // Scenario state
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [scenarioDocs, setScenarioDocs] = useState<ScenarioDoc[]>([]);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [stoppedEarlyMsg, setStoppedEarlyMsg] = useState<string | null>(null);

  useEffect(() => {
    api.getMembers()
      .then(setMembers)
      .catch(() => {})
      .finally(() => setMembersLoading(false));
    api.getTestCases()
      .then((data) => setTestCases(data.test_cases))
      .catch(() => {});
  }, []);

  // Rebuild upload slots when category changes (only when no scenario is active)
  useEffect(() => {
    if (!category) { setDocSlots([]); return; }
    const reqs = CATEGORY_DOC_REQUIREMENTS[category] ?? { required: [], optional: [] };
    const slots: DocSlot[] = [
      ...reqs.required.map((dt) => ({ id: dt + "_req", docType: dt, required: true, file: null, base64: "", preview: null })),
      ...reqs.optional.map((dt) => ({ id: dt + "_opt", docType: dt, required: false, file: null, base64: "", preview: null })),
    ];
    setDocSlots(slots);
  }, [category]);

  const updateSlot = (updated: DocSlot) => {
    setDocSlots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  };

  const addPriorClaim = () => {
    setPriorClaims((prev) => [...prev, { claim_id: `CLM_${Date.now()}`, date: "", amount: "", provider: "" }]);
  };

  const updatePriorClaim = (i: number, field: keyof PriorClaimInput, value: string) => {
    setPriorClaims((prev) => prev.map((c, idx) => idx === i ? { ...c, [field]: value } : c));
  };

  // ── Scenario handlers ─────────────────────────────────────────────────────

  const handleScenarioSelect = (caseId: string) => {
    setSelectedScenarioId(caseId);
    setError(null);
    setStoppedEarlyMsg(null);

    if (!caseId) {
      setScenarioDocs([]);
      return;
    }

    const tc = testCases.find((t) => t.case_id === caseId);
    if (!tc) return;
    const inp = tc.input;

    setMemberId(inp.member_id);
    setCategory(inp.claim_category);
    setTreatmentDate(inp.treatment_date);
    setClaimedAmount(String(inp.claimed_amount));
    setHospitalName(inp.hospital_name ?? "");
    setDiagnosis(inp.diagnosis ?? "");
    setYtdAmount(String(inp.ytd_claims_amount ?? 0));
    setSimFailure(inp.simulate_component_failure ?? false);

    if (inp.claims_history?.length) {
      setPriorClaims(inp.claims_history.map((c) => ({
        claim_id: c.claim_id,
        date: c.date,
        amount: String(c.amount),
        provider: c.provider,
      })));
    } else {
      setPriorClaims([]);
    }

    setScenarioDocs(inp.documents.map((d) => ({
      file_id: d.file_id,
      docType: d.actual_type ?? "UNKNOWN",
      quality: d.quality ?? null,
      content: d.content ?? null,
      fileName: d.file_name ?? `${d.file_id}.jpg`,
    })));
  };

  const clearScenario = () => {
    setSelectedScenarioId("");
    setScenarioDocs([]);
    setMemberId("");
    setCategory("");
    setTreatmentDate("");
    setClaimedAmount("");
    setHospitalName("");
    setDiagnosis("");
    setYtdAmount("0");
    setSimFailure(false);
    setPriorClaims([]);
    setError(null);
    setStoppedEarlyMsg(null);
  };

  // ── Form submit ───────────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStoppedEarlyMsg(null);

    if (!memberId) { setError("Please select a member."); return; }
    if (!category) { setError("Please select a claim category."); return; }
    if (!treatmentDate) { setError("Please enter the treatment date."); return; }
    if (!claimedAmount || parseFloat(claimedAmount) <= 0) { setError("Please enter a valid claimed amount."); return; }

    const hasScenarioDocs = scenarioDocs.length > 0;
    const uploadedDocs = docSlots.filter((s) => s.file !== null);

    if (!hasScenarioDocs && uploadedDocs.length === 0) {
      setError("Please upload at least one document.");
      return;
    }

    setSubmitting(true);
    setLoadingStep(0);

    const stepTimer = setInterval(() => {
      setLoadingStep((prev) => Math.min(prev + 1, STEPS.length - 1));
    }, 1200);

    try {
      const documents: UploadedDocument[] = hasScenarioDocs
        ? scenarioDocs.map((d) => ({
            file_id: d.file_id,
            file_name: d.fileName,
            file_content: "",
            actual_type: d.docType,
            quality: d.quality,
            content: d.content,
          }))
        : uploadedDocs.map((s) => ({
            file_id: `${s.docType}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            file_name: s.file!.name,
            file_content: s.base64,
            actual_type: null,
            quality: null,
          }));

      const history: PriorClaim[] = priorClaims
        .filter((c) => c.date && c.amount && c.provider)
        .map((c) => ({
          claim_id: c.claim_id,
          date: c.date,
          amount: parseFloat(c.amount),
          provider: c.provider,
        }));

      const result = await api.submitClaim({
        member_id: memberId,
        policy_id: "PLUM_GHI_2024",
        claim_category: category as ClaimCategory,
        treatment_date: treatmentDate,
        claimed_amount: parseFloat(claimedAmount),
        hospital_name: hospitalName || null,
        diagnosis: diagnosis || null,
        documents,
        claims_history: history.length > 0 ? history : null,
        ytd_claims_amount: parseFloat(ytdAmount) || 0,
        simulate_component_failure: simFailure,
      });

      if (result.status === "stopped_early") {
        setStoppedEarlyMsg(result.error_message ?? result.reasons?.[0] ?? "Claim could not be processed.");
        return;
      }

      router.push(`/claims/${result.claim_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      clearInterval(stepTimer);
      setSubmitting(false);
      setLoadingStep(0);
    }
  };

  const selectedMember = members.find((m) => m.member_id === memberId);
  const selectedScenario = testCases.find((t) => t.case_id === selectedScenarioId);

  return (
    <>
      {submitting && <LoadingOverlay step={loadingStep} />}

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Submit a Claim</h1>
          <p className="text-sm text-gray-500 mt-1">Fill in the details below. AI agents will verify, extract, and evaluate your claim automatically.</p>
        </div>

        {/* ── Test Scenario Loader ── */}
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">🧪</span>
            <h2 className="font-semibold text-violet-900 text-sm">Test Scenarios</h2>
            <span className="text-xs text-violet-500">— Select a pre-built scenario to auto-fill the form</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedScenarioId}
              onChange={(e) => handleScenarioSelect(e.target.value)}
              className="flex-1 h-9 rounded-lg border border-violet-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400/40 focus:border-violet-400 text-gray-700"
              disabled={testCases.length === 0}
            >
              <option value="">{testCases.length === 0 ? "Loading scenarios…" : "None — Manual Entry"}</option>
              {testCases.map((tc) => (
                <option key={tc.case_id} value={tc.case_id}>
                  {tc.case_id}: {TC_FRIENDLY_NAMES[tc.case_id] ?? tc.case_name}
                </option>
              ))}
            </select>
            {selectedScenarioId && (
              <button
                type="button"
                onClick={clearScenario}
                className="text-xs text-violet-600 hover:text-violet-800 border border-violet-200 hover:border-violet-300 bg-white rounded-lg px-3 py-1.5 font-medium transition-colors whitespace-nowrap"
              >
                Clear Scenario
              </button>
            )}
          </div>
          {selectedScenario && (
            <div className="mt-2.5 flex items-start gap-2 bg-violet-100/60 rounded-lg px-3 py-2 text-xs text-violet-800">
              <span className="shrink-0 mt-0.5">ℹ️</span>
              <span><strong>This scenario tests:</strong> {SCENARIO_DESCRIPTIONS[selectedScenario.case_id] ?? selectedScenario.description}</span>
            </div>
          )}
        </div>

        {error && (
          <Alert variant="destructive">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {stoppedEarlyMsg && (
          <Alert className="border-orange-300 bg-orange-50 text-orange-900">
            <svg className="w-4 h-4 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <AlertTitle className="text-orange-900">Claim Could Not Be Processed</AlertTitle>
            <AlertDescription className="text-orange-800">{stoppedEarlyMsg}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* ── Section 1: Member & Claim Details ── */}
          <Section title="Member & Claim Details">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Member *</Label>
                <select
                  value={memberId}
                  onChange={(e) => setMemberId(e.target.value)}
                  className="w-full h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500 disabled:opacity-50"
                  disabled={membersLoading}
                >
                  <option value="">{membersLoading ? "Loading…" : "Select member"}</option>
                  {members.map((m) => (
                    <option key={m.member_id} value={m.member_id}>
                      {m.name} ({m.member_id})
                    </option>
                  ))}
                </select>
                {selectedMember && (
                  <p className="text-xs text-teal-600">
                    {selectedMember.gender} · {selectedMember.relationship} · Joined {selectedMember.join_date ?? "—"}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label>Claim Category *</Label>
                <select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value as ClaimCategory);
                    // Clear scenario docs when user manually changes category
                    if (scenarioDocs.length > 0) {
                      setScenarioDocs([]);
                      setSelectedScenarioId("");
                    }
                  }}
                  className="w-full h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 focus:border-teal-500"
                >
                  <option value="">Select category</option>
                  {(["CONSULTATION","DIAGNOSTIC","PHARMACY","DENTAL","VISION","ALTERNATIVE_MEDICINE"] as ClaimCategory[]).map((c) => (
                    <option key={c} value={c}>{c.replace("_", " ")}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Treatment Date *</Label>
                <Input
                  type="date"
                  value={treatmentDate}
                  onChange={(e) => setTreatmentDate(e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Claimed Amount (INR) *</Label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">₹</span>
                  <Input
                    type="number"
                    min="1"
                    step="0.01"
                    value={claimedAmount}
                    onChange={(e) => setClaimedAmount(e.target.value)}
                    className="pl-7 h-9"
                    placeholder="0.00"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Hospital / Clinic Name</Label>
                <Input
                  value={hospitalName}
                  onChange={(e) => setHospitalName(e.target.value)}
                  placeholder="e.g. Apollo Hospitals"
                  className="h-9"
                />
                <p className="text-xs text-gray-400">Network hospitals receive a discount</p>
              </div>
              <div className="space-y-1.5">
                <Label>Diagnosis</Label>
                <Input
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="e.g. Viral fever"
                  className="h-9"
                />
                <p className="text-xs text-gray-400">Helps with exclusion & waiting period checks</p>
              </div>
            </div>
          </Section>

          {/* ── Section 2: Documents ── */}
          {category ? (
            <Section
              title="Documents"
              description={
                scenarioDocs.length > 0
                  ? `${scenarioDocs.length} test document(s) pre-loaded from scenario ${selectedScenarioId}. You can still submit manually uploaded files instead.`
                  : `Required documents for ${category.replace("_", " ")} claims are marked below.`
              }
            >
              {scenarioDocs.length > 0 ? (
                <div className="space-y-2">
                  {scenarioDocs.map((doc) => (
                    <TestDocCard key={doc.file_id} doc={doc} />
                  ))}
                  <p className="text-xs text-gray-400 pt-1">These pre-populated test documents will be submitted directly without file upload.</p>
                </div>
              ) : docSlots.length === 0 ? (
                <p className="text-sm text-gray-500">No document requirements configured for this category.</p>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {docSlots.map((slot) => (
                    <DocUploadSlot key={slot.id} slot={slot} onChange={updateSlot} />
                  ))}
                </div>
              )}
            </Section>
          ) : (
            <Card className="border-dashed">
              <CardContent className="py-8 flex flex-col items-center gap-2 text-gray-400">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-sm">Select a claim category to see document requirements</p>
              </CardContent>
            </Card>
          )}

          {/* ── Section 3: Additional Info ── */}
          <Section title="Additional Information" description="Optional — used for limit checks and fraud detection testing.">
            <div className="space-y-1.5">
              <Label>Year-to-Date Claims Amount (INR)</Label>
              <div className="relative max-w-xs">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">₹</span>
                <Input
                  type="number"
                  min="0"
                  value={ytdAmount}
                  onChange={(e) => setYtdAmount(e.target.value)}
                  className="pl-7 h-9"
                  placeholder="0"
                />
              </div>
            </div>

            {/* Prior claims */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Previous Claims (for fraud detection testing)</Label>
                <button type="button" onClick={addPriorClaim}
                  className="text-xs text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4"/></svg>
                  Add claim
                </button>
              </div>
              {priorClaims.map((c, i) => (
                <div key={i} className="grid grid-cols-4 gap-2 items-center bg-gray-50 rounded-lg p-2">
                  <Input type="date" value={c.date} onChange={(e) => updatePriorClaim(i, "date", e.target.value)} className="h-8 text-xs" />
                  <Input type="number" value={c.amount} placeholder="Amount" onChange={(e) => updatePriorClaim(i, "amount", e.target.value)} className="h-8 text-xs" />
                  <Input value={c.provider} placeholder="Provider" onChange={(e) => updatePriorClaim(i, "provider", e.target.value)} className="h-8 text-xs" />
                  <button type="button" onClick={() => setPriorClaims((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-gray-400 hover:text-red-500 text-xs justify-self-center">✕</button>
                </div>
              ))}
            </div>

            {/* Simulate failure */}
            <label className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="checkbox"
                checked={simFailure}
                onChange={(e) => setSimFailure(e.target.checked)}
                className="w-4 h-4 rounded accent-teal-600"
              />
              <div>
                <span className="text-sm font-medium text-gray-700 group-hover:text-gray-900">Simulate component failure</span>
                <p className="text-xs text-gray-400">Tests graceful degradation (TC011) — pipeline continues with reduced confidence</p>
              </div>
            </label>
          </Section>

          {/* ── Submit ── */}
          <div className="flex items-center justify-between pt-2">
            {claimedAmount && memberId && (
              <p className="text-sm text-gray-500">
                Submitting <span className="font-semibold text-gray-900">{formatINR(parseFloat(claimedAmount))}</span>
                {" "}for <span className="font-semibold text-gray-900">{selectedMember?.name ?? memberId}</span>
                {selectedScenarioId && <span className="ml-1 text-violet-500 text-xs">(Scenario {selectedScenarioId})</span>}
              </p>
            )}
            <Button
              type="submit"
              disabled={submitting}
              className="bg-teal-600 hover:bg-teal-700 text-white ml-auto"
            >
              {submitting ? "Processing…" : "Submit Claim →"}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}
