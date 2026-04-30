"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, formatINR, DECISION_CONFIG } from "@/lib/api";
import type { ClaimResponse, PolicyEvalSummary } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress, ProgressTrack, ProgressIndicator } from "@/components/ui/progress";
import { TraceViewer } from "@/components/TraceViewer";

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ClaimDetailPage() {
  const params = useParams();
  const claimId = params?.id as string;
  const [claim, setClaim] = useState<ClaimResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!claimId) return;
    api.getClaim(claimId).then(setClaim).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [claimId]);

  if (loading)
    return <div className="flex items-center justify-center py-32 text-gray-400 gap-3"><div className="w-5 h-5 border-2 border-gray-300 border-t-teal-600 rounded-full animate-spin"/>Loading claim…</div>;

  if (error)
    return <div className="max-w-2xl mx-auto px-4 py-12 text-center"><p className="text-red-600 mb-4">{error}</p><Link href="/claims" className="text-teal-600 hover:underline text-sm">← Back to all claims</Link></div>;

  if (!claim) return null;

  const cfg = claim.decision ? DECISION_CONFIG[claim.decision] : null;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link href="/claims" className="hover:text-teal-600">All Claims</Link>
        <span>›</span>
        <span className="font-mono text-gray-700">{claimId}</span>
      </div>

      {/* ── Verdict card ── */}
      <Card className={`border-2 ${cfg?.border ?? "border-gray-200"} ${cfg?.bg ?? "bg-white"}`}>
        <CardContent className="pt-6 pb-6">
          {claim.status === "stopped_early" ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                  <svg className="w-5 h-5 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                </div>
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Claim Stopped Early</h2>
                  <p className="text-sm text-gray-500">Processing could not continue</p>
                </div>
              </div>
              {claim.error_message && <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm text-orange-800">{claim.error_message}</div>}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className={`text-2xl font-bold ${cfg?.text ?? "text-gray-900"}`}>{cfg?.label ?? claim.decision ?? "Processing"}</h2>
                    {claim.decision && <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${cfg?.badgeBg} ${cfg?.badgeText}`}>{claim.decision}</span>}
                  </div>
                  <p className="text-sm text-gray-500">
                    Claim <span className="font-mono font-medium text-gray-700">{claimId}</span>
                    {claim.trace?.total_duration_ms && <span className="ml-2 text-gray-400">· {claim.trace.total_duration_ms.toFixed(0)}ms total</span>}
                  </p>
                </div>
                {claim.approved_amount != null && (
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{formatINR(claim.approved_amount)}</p>
                    <p className="text-xs text-gray-400 mt-0.5">Approved amount</p>
                  </div>
                )}
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Confidence score</span>
                  <span className="font-semibold text-gray-700">{Math.round(claim.confidence_score * 100)}%</span>
                </div>
                <Progress value={claim.confidence_score * 100}>
                  <ProgressTrack className="h-2">
                    <ProgressIndicator className={`h-full rounded-full ${claim.confidence_score > 0.8 ? "bg-teal-500" : claim.confidence_score > 0.5 ? "bg-amber-500" : "bg-red-500"}`}/>
                  </ProgressTrack>
                </Progress>
              </div>

              {(claim.reasons?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  {claim.reasons.map((r, i) => <p key={i} className="text-sm text-gray-700 flex items-start gap-2"><span className="text-gray-400 mt-0.5 shrink-0">·</span><span>{r}</span></p>)}
                </div>
              )}
              {(claim.recommendations?.length ?? 0) > 0 && (
                <div className="bg-teal-50 border border-teal-100 rounded-lg p-3 space-y-1">
                  <p className="text-xs font-semibold text-teal-700 uppercase tracking-wide">Recommendations</p>
                  {claim.recommendations.map((r, i) => <p key={i} className="text-sm text-teal-700">· {r}</p>)}
                </div>
              )}
              {(claim.errors?.length ?? 0) > 0 && (
                <div className="bg-red-50 border border-red-100 rounded-lg p-3 space-y-1">
                  <p className="text-xs font-semibold text-red-600 uppercase tracking-wide">Processing Errors</p>
                  {claim.errors.map((e, i) => <p key={i} className="text-sm text-red-700">· {e}</p>)}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Trace accordion ── */}
      {(claim.trace?.entries?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Decision Trace</CardTitle>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                {claim.trace!.entries.length} agents · {claim.trace!.total_duration_ms?.toFixed(0)}ms
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <TraceViewer trace={claim.trace!} />
          </CardContent>
        </Card>
      )}

      {/* ── Line items for PARTIAL ── */}
      {claim.decision === "PARTIAL" && (() => {
        const policyEntry = claim.trace?.entries.find((e) => e.agent_name === "PolicyEvaluation");
        const lineItems = (policyEntry?.summary as unknown as PolicyEvalSummary)?.line_item_results;
        if (!lineItems?.length) return null;
        return (
          <Card>
            <CardHeader><CardTitle className="text-base">Line Item Breakdown</CardTitle></CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Description</th>
                    <th className="text-right py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                    <th className="text-center py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                    <th className="text-left py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {lineItems.map((li, i) => (
                    <tr key={i}>
                      <td className="py-2 text-gray-700">{li.description}</td>
                      <td className="py-2 text-right font-medium tabular-nums">{formatINR(li.amount)}</td>
                      <td className="py-2 text-center"><span className={`inline-flex text-xs px-2 py-0.5 rounded-full font-medium ${li.status === "approved" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{li.status}</span></td>
                      <td className="py-2 text-xs text-gray-400">{li.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        );
      })()}
    </div>
  );
}
