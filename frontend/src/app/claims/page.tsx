"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api, formatINR, DECISION_CONFIG } from "@/lib/api";

interface ClaimSummary {
  claim_id: string;
  status: string;
  decision: string | null;
  approved_amount: number | null;
  confidence_score: number;
}

export default function AllClaimsPage() {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchClaims = () => {
    setLoading(true);
    api.getAllClaims()
      .then((data) => { setClaims(data as ClaimSummary[]); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchClaims(); }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">All Claims</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {claims.length} claim{claims.length !== 1 ? "s" : ""} processed
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchClaims}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <Link
            href="/"
            className="bg-teal-600 hover:bg-teal-700 text-white text-sm px-3 py-1.5 rounded-lg transition-colors font-medium"
          >
            + New Claim
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm mb-4">
          {error} — is the backend running at localhost:8000?
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-400 gap-3">
          <div className="w-5 h-5 border-2 border-gray-300 border-t-teal-600 rounded-full animate-spin" />
          Loading claims…
        </div>
      ) : claims.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No claims processed yet</p>
          <p className="text-gray-400 text-sm mt-1">Submit a claim to get started</p>
          <Link
            href="/"
            className="inline-block mt-4 bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-2 rounded-lg transition-colors font-medium"
          >
            Submit a Claim
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Claim ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Decision</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Approved Amount</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Confidence</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {claims.map((claim) => {
                const cfg = claim.decision ? DECISION_CONFIG[claim.decision] : null;
                return (
                  <tr key={claim.claim_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{claim.claim_id}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full font-medium ${
                        claim.status === "completed"
                          ? "bg-gray-100 text-gray-700"
                          : "bg-orange-100 text-orange-700"
                      }`}>
                        {claim.status === "completed" ? "Completed" : "Stopped Early"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {cfg ? (
                        <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full font-medium ${cfg.badgeBg} ${cfg.badgeText}`}>
                          {cfg.label}
                        </span>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      {claim.approved_amount != null ? formatINR(claim.approved_amount) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-teal-500 rounded-full"
                            style={{ width: `${claim.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 tabular-nums w-8 text-right">
                          {Math.round(claim.confidence_score * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/claims/${claim.claim_id}`}
                        className="text-teal-600 hover:text-teal-700 font-medium text-xs"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
