"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SampleDoc {
  filename: string;
  label: string;
  description: string;
}

interface DocSet {
  id: string;
  scenario: string;
  title: string;
  description: string;
  howToTest: string;
  expectedOutcome: string;
  outcomeColor: "green" | "amber" | "orange" | "blue";
  docs: SampleDoc[];
}

// ── Data ──────────────────────────────────────────────────────────────────────

const DOC_SETS: DocSet[] = [
  {
    id: "TC004",
    scenario: "TC004",
    title: "Clean Consultation Approval",
    description: "Standard consultation at City Medical Centre. Complete, valid documents with correct patient name across both.",
    howToTest: "Member: EMP001 · Category: CONSULTATION · Amount: ₹1,500 · Date: 2024-11-01",
    expectedOutcome: "APPROVED — ₹1,350 (10% co-pay deducted)",
    outcomeColor: "green",
    docs: [
      {
        filename: "prescription_rajesh_consultation.jpg",
        label: "Prescription",
        description: "Dr. Arun Sharma — Viral Fever",
      },
      {
        filename: "hospital_bill_rajesh_consultation.jpg",
        label: "Hospital Bill",
        description: "City Medical Centre — ₹1,500",
      },
    ],
  },
  {
    id: "TC010",
    scenario: "TC010",
    title: "Network Hospital Discount",
    description: "Consultation at Apollo Hospitals (network hospital). Tests that 20% network discount is applied before the 10% co-pay — order matters.",
    howToTest: "Member: EMP002 · Category: CONSULTATION · Amount: ₹4,500 · Hospital: Apollo Hospitals · Date: 2024-10-15",
    expectedOutcome: "APPROVED — ₹3,240 (20% network discount → 10% co-pay)",
    outcomeColor: "green",
    docs: [
      {
        filename: "prescription_priya_consultation.jpg",
        label: "Prescription",
        description: "Dr. Meena Reddy — Apollo Hospitals",
      },
      {
        filename: "hospital_bill_priya_apollo.jpg",
        label: "Hospital Bill",
        description: "Apollo Hospitals — ₹4,500",
      },
    ],
  },
  {
    id: "TC006",
    scenario: "TC006",
    title: "Dental Partial Approval",
    description: "Dental bill with two line items: Root Canal Treatment (covered) and Teeth Whitening (cosmetic, excluded by policy).",
    howToTest: "Member: EMP002 · Category: DENTAL · Amount: ₹12,000 · Date: 2024-10-20",
    expectedOutcome: "PARTIAL — ₹8,000 approved (Teeth Whitening ₹4,000 excluded)",
    outcomeColor: "amber",
    docs: [
      {
        filename: "dental_bill_amit.jpg",
        label: "Dental Bill",
        description: "Smile Dental Clinic — RCT + Whitening",
      },
    ],
  },
  {
    id: "TC002",
    scenario: "TC002",
    title: "Blurry Document Detection",
    description: "Pharmacy claim with a clear prescription and a deliberately blurry pharmacy bill. GPT-4o Vision detects the unreadable document.",
    howToTest: "Member: EMP004 · Category: PHARMACY · Amount: ₹380 · Date: 2024-11-10",
    expectedOutcome: "STOPPED EARLY — system requests re-upload of blurry bill",
    outcomeColor: "orange",
    docs: [
      {
        filename: "prescription_sneha_pharmacy.jpg",
        label: "Prescription (clear)",
        description: "Dr. Priya Mehta — Acute Gastritis",
      },
      {
        filename: "pharmacy_bill_sneha_blurry.jpg",
        label: "Pharmacy Bill (blurry)",
        description: "MedPlus — intentionally unreadable",
      },
    ],
  },
  {
    id: "LAB",
    scenario: "Generic",
    title: "Lab Report",
    description: "CBC and Dengue NS1 test results from a NABL-accredited lab. Use as an optional document with any Consultation or Diagnostic claim.",
    howToTest: "Add as LAB REPORT in any Consultation claim for Member EMP001",
    expectedOutcome: "Extracted normally — all results within normal range",
    outcomeColor: "blue",
    docs: [
      {
        filename: "lab_report_sample.jpg",
        label: "Lab Report",
        description: "Precision Diagnostics — CBC + Dengue NS1",
      },
    ],
  },
];

const OUTCOME_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  green:  { bg: "bg-emerald-50",  text: "text-emerald-800", dot: "bg-emerald-500"  },
  amber:  { bg: "bg-amber-50",    text: "text-amber-800",   dot: "bg-amber-500"    },
  orange: { bg: "bg-orange-50",   text: "text-orange-800",  dot: "bg-orange-500"   },
  blue:   { bg: "bg-blue-50",     text: "text-blue-800",    dot: "bg-blue-500"     },
};

// ── Document thumbnail ────────────────────────────────────────────────────────

function DocThumb({ doc }: { doc: SampleDoc }) {
  return (
    <div className="flex flex-col gap-2">
      <a
        href={`/sample-documents/${doc.filename}`}
        target="_blank"
        rel="noopener noreferrer"
        className="block group"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`/sample-documents/${doc.filename}`}
          alt={doc.label}
          className="w-full rounded-lg border border-gray-200 shadow-sm group-hover:shadow-md group-hover:border-teal-300 transition-all duration-200 object-cover"
          style={{ aspectRatio: "8/11", objectPosition: "top" }}
        />
      </a>
      <div className="space-y-1">
        <p className="text-xs font-semibold text-gray-800">{doc.label}</p>
        <p className="text-xs text-gray-500 leading-snug">{doc.description}</p>
        <a
          href={`/sample-documents/${doc.filename}`}
          download={doc.filename}
          className="inline-flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700 font-medium mt-1"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download
        </a>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-xl font-semibold text-gray-900">Sample Medical Documents</h1>
        <p className="text-sm text-gray-500 max-w-2xl">
          Realistic Indian medical documents generated for testing. Upload these on the{" "}
          <Link href="/" className="text-teal-600 hover:underline font-medium">Submit Claim</Link>{" "}
          page (manual entry mode) to test real GPT-4o Vision processing through the full pipeline.
        </p>
      </div>

      {/* How to use callout */}
      <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 flex gap-3">
        <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0 mt-0.5">
          <svg className="w-4 h-4 text-teal-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="text-sm text-teal-900 space-y-1">
          <p className="font-semibold">How to test with real documents</p>
          <ol className="text-teal-800 space-y-0.5 list-decimal list-inside">
            <li>Download the documents for a scenario below</li>
            <li>Go to <Link href="/" className="underline">Submit Claim</Link> and select <strong>None — Manual Entry</strong> in the scenario dropdown</li>
            <li>Fill in the member, category, amount, and date from the "How to test" instructions</li>
            <li>Upload the downloaded documents in the Documents section</li>
            <li>Submit — GPT-4o Vision will read and process them through all 6 agents</li>
          </ol>
        </div>
      </div>

      {/* Document sets */}
      {DOC_SETS.map((set) => {
        const outcome = OUTCOME_STYLES[set.outcomeColor];
        return (
          <Card key={set.id}>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-semibold">
                      {set.scenario}
                    </span>
                    <CardTitle className="text-base">{set.title}</CardTitle>
                  </div>
                  <CardDescription className="text-sm leading-relaxed">
                    {set.description}
                  </CardDescription>
                </div>
                {/* Download all button */}
                <div className="flex flex-col gap-1 shrink-0">
                  {set.docs.map((doc) => (
                    <a
                      key={doc.filename}
                      href={`/sample-documents/${doc.filename}`}
                      download={doc.filename}
                      className="text-xs text-gray-500 hover:text-teal-600 whitespace-nowrap"
                    >
                      ↓ {doc.label}
                    </a>
                  ))}
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Document thumbnails */}
              <div className={`grid gap-4 ${set.docs.length === 1 ? "grid-cols-1 max-w-[200px]" : `grid-cols-${Math.min(set.docs.length, 4)}`}`}
                   style={{ gridTemplateColumns: `repeat(${Math.min(set.docs.length, 4)}, minmax(0, 180px))` }}>
                {set.docs.map((doc) => (
                  <DocThumb key={doc.filename} doc={doc} />
                ))}
              </div>

              {/* Test instructions */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="bg-gray-50 rounded-lg p-3 space-y-1">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">How to test</p>
                  <p className="text-xs text-gray-700 leading-relaxed">{set.howToTest}</p>
                </div>
                <div className={`${outcome.bg} rounded-lg p-3 space-y-1`}>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${outcome.text} opacity-70`}>Expected outcome</p>
                  <div className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${outcome.dot} shrink-0`} />
                    <p className={`text-xs font-medium ${outcome.text} leading-relaxed`}>{set.expectedOutcome}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}

      {/* Footer note */}
      <div className="text-center py-4 space-y-1">
        <p className="text-xs text-gray-400">
          All documents are 800×1100 px JPEG — generated from{" "}
          <code className="bg-gray-100 px-1 rounded text-gray-600">backend/scripts/generate_mock_docs.py</code>
        </p>
        <p className="text-xs text-gray-400">
          No real patient data — for demonstration purposes only.
        </p>
      </div>
    </div>
  );
}
