"use client";

import { useState, useEffect } from "react";
import { api, formatINR, DECISION_CONFIG } from "@/lib/api";
import type { EvalSingleResult, TestCase } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TraceViewer, AgentTimingRow } from "@/components/TraceViewer";

// ── Decision badge ────────────────────────────────────────────────────────────

function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) return <span className="text-xs text-gray-400 font-mono">STOP</span>;
  const cfg = DECISION_CONFIG[decision];
  if (!cfg) return <span className="text-xs font-mono text-gray-600">{decision}</span>;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${cfg.badgeBg} ${cfg.badgeText}`}>
      {decision}
    </span>
  );
}

// ── Result row ────────────────────────────────────────────────────────────────

function ResultRow({
  tc,
  result,
  isRunning,
  onRunSingle,
}: {
  tc: TestCase;
  result: EvalSingleResult | null;
  isRunning: boolean;
  onRunSingle: (caseId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const passIcon = result?.passed ? (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100">
      <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    </span>
  ) : result ? (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-100">
      <svg className="w-3.5 h-3.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </span>
  ) : null;

  const rowBg = isRunning
    ? "bg-violet-50"
    : result && !result.passed
    ? "bg-red-50/30"
    : "";

  return (
    <>
      <tr className={`border-b border-gray-100 transition-colors ${rowBg} ${result ? "cursor-pointer hover:bg-gray-50" : ""}`}
        onClick={() => result && setExpanded((v) => !v)}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-gray-700">{tc.case_id}</span>
            {isRunning && (
              <span className="w-3.5 h-3.5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-sm text-gray-700 max-w-[200px]">
          <span className="truncate block">{tc.case_name}</span>
        </td>
        <td className="px-4 py-3">
          {result ? <DecisionBadge decision={result.expected_decision} /> : <span className="text-gray-300 text-xs">—</span>}
        </td>
        <td className="px-4 py-3">
          {result ? <DecisionBadge decision={result.actual_decision} /> : isRunning ? (
            <span className="text-xs text-violet-500 animate-pulse">Running…</span>
          ) : <span className="text-gray-300 text-xs">—</span>}
        </td>
        <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-600">
          {result?.expected_amount != null ? formatINR(result.expected_amount) : "—"}
        </td>
        <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-600">
          {result?.actual_amount != null ? formatINR(result.actual_amount) : "—"}
        </td>
        <td className="px-4 py-3 text-right text-xs text-gray-400 tabular-nums">
          {result ? `${result.duration_ms}ms` : "—"}
        </td>
        <td className="px-4 py-3 text-center">{passIcon}</td>
        <td className="px-4 py-3 text-right">
          <button
            onClick={(e) => { e.stopPropagation(); onRunSingle(tc.case_id); }}
            disabled={isRunning}
            className="text-xs text-teal-600 hover:text-teal-700 disabled:opacity-40 disabled:cursor-not-allowed font-medium border border-teal-200 hover:border-teal-300 rounded px-2 py-0.5 transition-colors"
          >
            {isRunning ? "…" : "Run"}
          </button>
        </td>
      </tr>

      {expanded && result && (
        <tr className="bg-gray-50/80">
          <td colSpan={9} className="px-4 pb-4 pt-2">
            <div className="space-y-3">
              {/* Per-agent timing */}
              {Object.keys(result.agent_timing ?? {}).length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Agent Timing</p>
                  <AgentTimingRow timing={result.agent_timing} />
                </div>
              )}

              {/* Error / failure info */}
              {result.error_message && (
                <div className="bg-orange-50 border border-orange-200 rounded-lg p-2.5 text-orange-800 text-xs">
                  <strong>Error:</strong> {result.error_message}
                </div>
              )}
              {!result.passed && result.reason && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2.5 text-red-700 text-xs">
                  <strong>Failure reason:</strong> {result.reason}
                </div>
              )}

              {/* Decision reasons */}
              {(result.reasons?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Decision Reasons</p>
                  <div className="space-y-0.5">
                    {result.reasons.map((r, i) => (
                      <p key={i} className="text-xs text-gray-600 flex items-start gap-1.5"><span className="text-gray-400 shrink-0">·</span>{r}</p>
                    ))}
                  </div>
                </div>
              )}

              {/* Full trace */}
              {result.trace?.entries?.length ? (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Full Agent Trace</p>
                  <div className="border border-gray-200 rounded-lg bg-white p-3">
                    <TraceViewer trace={result.trace} defaultExpanded={false} />
                  </div>
                </div>
              ) : null}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main eval page ────────────────────────────────────────────────────────────

export default function EvalPage() {
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [results, setResults] = useState<Record<string, EvalSingleResult>>({});
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [progressLog, setProgressLog] = useState<Array<{ id: string; passed: boolean }>>([]);
  const [currentRunningLabel, setCurrentRunningLabel] = useState<string | null>(null);
  const [totalDurationMs, setTotalDurationMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<Date | null>(null);

  useEffect(() => {
    api.getTestCases()
      .then((data) => setTestCases(data.test_cases))
      .catch(() => {});
  }, []);

  const runSingle = async (caseId: string) => {
    setRunningIds((prev) => new Set([...prev, caseId]));
    try {
      const result = await api.runSingleEval(caseId);
      setResults((prev) => ({ ...prev, [caseId]: result }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed — is the backend running?");
    } finally {
      setRunningIds((prev) => { const s = new Set(prev); s.delete(caseId); return s; });
    }
  };

  const runAll = async () => {
    if (testCases.length === 0) return;
    setIsRunningAll(true);
    setError(null);
    setResults({});
    setProgressLog([]);
    setCurrentRunningLabel(null);
    setTotalDurationMs(null);

    const t0 = Date.now();
    try {
      for (let i = 0; i < testCases.length; i++) {
        const tc = testCases[i];
        setCurrentRunningLabel(`Running ${tc.case_id} (${i + 1} of ${testCases.length}): ${tc.case_name}`);
        setRunningIds(new Set([tc.case_id]));

        const result = await api.runSingleEval(tc.case_id);
        setResults((prev) => ({ ...prev, [tc.case_id]: result }));
        setProgressLog((prev) => [...prev, { id: tc.case_id, passed: result.passed }]);
        setRunningIds(new Set());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eval failed — is the backend running?");
    } finally {
      setIsRunningAll(false);
      setRunningIds(new Set());
      setCurrentRunningLabel(null);
      setTotalDurationMs(Date.now() - t0);
      setLastRun(new Date());
    }
  };

  const completedCount = Object.keys(results).length;
  const passCount = Object.values(results).filter((r) => r.passed).length;
  const allDone = completedCount === testCases.length && testCases.length > 0;
  const passRate = completedCount > 0 ? Math.round((passCount / completedCount) * 100) : null;
  const totalMs = Object.values(results).reduce((sum, r) => sum + (r.duration_ms ?? 0), 0);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Evaluation Suite</h1>
          <p className="text-sm text-gray-500 mt-1">
            Run all 12 test cases one-by-one and inspect each agent&apos;s output.
            {lastRun && <span className="ml-2 text-gray-400">Last run: {lastRun.toLocaleTimeString()}</span>}
          </p>
        </div>
        <Button
          onClick={runAll}
          disabled={isRunningAll || testCases.length === 0}
          className="bg-teal-600 hover:bg-teal-700 text-white font-medium shrink-0"
        >
          {isRunningAll ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              Running…
            </span>
          ) : allDone ? "Run Again" : "Run All 12 Test Cases"}
        </Button>
      </div>

      {/* ── Live progress ── */}
      {isRunningAll && (
        <Card className="border-violet-200 bg-violet-50">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
              <p className="text-sm font-medium text-violet-900">{currentRunningLabel ?? "Initialising…"}</p>
            </div>
            {/* Progress bar */}
            <div className="h-1.5 bg-violet-200 rounded-full overflow-hidden mb-3">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-500"
                style={{ width: `${(progressLog.length / (testCases.length || 1)) * 100}%` }}
              />
            </div>
            {/* Completed log */}
            {progressLog.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {progressLog.map(({ id, passed }) => (
                  <span key={id} className={`text-xs px-2 py-0.5 rounded-full font-mono font-semibold ${passed ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                    {id} {passed ? "✓" : "✗"}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">{error}</div>
      )}

      {/* ── Summary card ── */}
      {allDone && !isRunningAll && (
        <Card className={`border-2 ${passCount === testCases.length ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
          <CardContent className="pt-6 pb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-4xl font-bold ${passCount === testCases.length ? "text-emerald-700" : "text-amber-700"}`}>
                  {passCount}/{testCases.length}
                </p>
                <p className={`text-sm font-medium mt-1 ${passCount === testCases.length ? "text-emerald-600" : "text-amber-600"}`}>
                  Test cases passed · {passRate}% pass rate
                </p>
                {totalDurationMs != null && (
                  <p className="text-xs text-gray-500 mt-1">
                    Total wall time: {(totalDurationMs / 1000).toFixed(1)}s · Pipeline time: {totalMs}ms
                  </p>
                )}
              </div>
              <div className="text-right">
                {passCount === testCases.length ? (
                  <div className="flex items-center gap-2 text-emerald-700">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="font-semibold text-lg">All Passing</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-600">
                    <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="font-semibold text-lg">{testCases.length - passCount} Failing</span>
                  </div>
                )}
              </div>
            </div>
            {/* Mini pass/fail strip */}
            <div className="mt-4 flex gap-1">
              {testCases.map((tc) => {
                const r = results[tc.case_id];
                return (
                  <div
                    key={tc.case_id}
                    title={`${tc.case_id}: ${r?.passed ? "PASS" : "FAIL"}`}
                    className={`flex-1 h-2 rounded-sm ${!r ? "bg-gray-200" : r.passed ? "bg-emerald-500" : "bg-red-500"}`}
                  />
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Results table ── */}
      {(testCases.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Test Case Results</CardTitle>
            <CardDescription>
              {completedCount > 0
                ? `${completedCount} of ${testCases.length} completed — click a row to expand the full trace`
                : "Click \"Run All 12 Test Cases\" to start, or use the Run button on individual rows"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Case</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Expected</th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Actual</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Exp. Amt</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Act. Amt</th>
                    <th className="text-right px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Time</th>
                    <th className="text-center px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Result</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {testCases.map((tc) => (
                    <ResultRow
                      key={tc.case_id}
                      tc={tc}
                      result={results[tc.case_id] ?? null}
                      isRunning={runningIds.has(tc.case_id)}
                      onRunSingle={runSingle}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Info cards (shown before first run) ── */}
      {completedCount === 0 && !isRunningAll && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { id: "TC001–TC003", title: "Document Checks", desc: "Wrong docs, unreadable files, name mismatches — tests Agent 1 & 3 with specific error messages" },
            { id: "TC004–TC008", title: "Policy Rules", desc: "Approvals, waiting periods, exclusions, pre-auth, per-claim limits — tests pure-logic Agent 4" },
            { id: "TC009–TC012", title: "Edge Cases", desc: "Fraud detection, network discounts, component failure, excluded treatments" },
          ].map((g) => (
            <Card key={g.id} size="sm">
              <CardContent className="pt-4 pb-4">
                <p className="font-mono text-xs text-teal-600 font-semibold mb-1">{g.id}</p>
                <p className="font-medium text-gray-900 text-sm mb-1">{g.title}</p>
                <p className="text-xs text-gray-500">{g.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
