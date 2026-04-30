# Plum Claims Processor — AI-Powered Health Insurance Claims System

> Multi-agent AI system that automates health insurance claim processing using 6 specialized agents orchestrated by LangGraph. Built for the Plum AI Engineer assignment.

## Live Demo

| Service | URL |
|---------|-----|
| Frontend | *(Vercel URL — to be added after deployment)* |
| Backend API | *(Railway URL — to be added after deployment)* |
| API Docs | `{Railway URL}/docs` |

---

## Architecture

```
Submitted Claim
       │
       ▼
┌─────────────────────┐
│ Document Verification│  Checks types, presence, and readability of uploaded docs
└──────────┬──────────┘
           │  stops early if docs are wrong/missing/unreadable
           ▼
┌─────────────────────┐
│ Document Extraction  │  GPT-4o Vision extracts structured data from each document
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Cross-Validation   │  Checks patient name consistency, date/amount matches
└──────────┬──────────┘
           │  stops early if documents contradict each other
           ▼
┌─────────────────────┐
│  Policy Evaluation  │  Deterministic engine: waiting periods, exclusions,
│                     │  pre-auth, per-claim limits, annual limits, financials
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Fraud Detection    │  Flags same-day duplicates, high-value anomalies,
│                     │  unusual claim patterns
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Decision Aggregation│  Combines all signals → APPROVED / PARTIAL / REJECTED
│                     │  / MANUAL_REVIEW with confidence score and full trace
└─────────────────────┘
```

**Key design properties:**
- Each agent runs independently and emits a structured trace entry
- Any agent can short-circuit the pipeline by raising a `StoppedEarly` signal
- If an agent fails (e.g. TC011), the pipeline degrades gracefully rather than crashing
- Every decision includes a full observability trace showing each agent's reasoning

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.11, FastAPI, Uvicorn |
| Agent orchestration | LangGraph |
| LLM | OpenAI GPT-4o (Vision for documents) |
| Data validation | Pydantic v2 |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| UI components | shadcn/ui (base-ui primitives) |
| Deployment — frontend | Vercel |
| Deployment — backend | Railway (Docker) |

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (GPT-4o access)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=sk-...

uvicorn main:app --reload
```

Backend runs at **http://localhost:8000** — interactive API docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:3000**.

> The frontend reads `NEXT_PUBLIC_API_URL` from `frontend/.env.local` (defaults to `http://localhost:8000`).

---

## How to Use

### Submit a Claim

Navigate to `/` (home). You can either:

**Use a test scenario** — select from the "🧪 Test Scenarios" dropdown at the top. All 12 pre-built scenarios auto-fill the form including member, dates, amounts, and documents. No file upload needed.

**Submit manually** — fill in member details, select a category, upload document images (JPG/PNG/PDF), and click Submit. GPT-4o Vision processes real documents.

### View Decision Trace

After submission, the decision page shows:
- Final verdict (APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW) with amount
- Confidence score
- Full per-agent trace with expandable panels showing each agent's internal reasoning

### Eval Suite

Navigate to `/eval`. Click **Run All 12 Test Cases** to execute the full evaluation suite — cases run one at a time with a live progress indicator. Click any completed row to expand the full trace. Individual cases can also be re-run via the **Run** button on each row.

---

## Test Results

All 12 test cases pass. The eval suite covers:

| Cases | Category | What it tests |
|-------|----------|---------------|
| TC001–TC003 | Document checks | Wrong doc type, unreadable quality, cross-patient name mismatch |
| TC004–TC008 | Policy rules | Standard approval, waiting periods, exclusions, pre-auth, per-claim limits |
| TC009–TC012 | Edge cases | Fraud detection, network hospital discount, component failure, excluded conditions |

Run the eval from the CLI:

```bash
cd backend
python -m scripts.run_eval
```

---

## Project Structure

```
plum-claims-processor/
├── backend/
│   ├── agents/
│   │   ├── document_verification.py   # Agent 1 — type checks, quality
│   │   ├── document_extraction.py     # Agent 2 — GPT-4o Vision extraction
│   │   ├── cross_validation.py        # Agent 3 — consistency checks
│   │   ├── policy_evaluation.py       # Agent 4 — deterministic policy engine
│   │   ├── fraud_detection.py         # Agent 5 — anomaly detection
│   │   └── decision_aggregation.py    # Agent 6 — final verdict
│   ├── orchestrator/
│   │   └── pipeline.py                # LangGraph state machine
│   ├── models/                        # Pydantic models (claim, decision, trace)
│   ├── services/                      # LLM service, policy loader
│   ├── data/
│   │   ├── policy_terms.json          # Policy rules and limits
│   │   └── test_cases.json            # 12 evaluation test cases
│   ├── tests/                         # Unit and integration tests
│   ├── scripts/
│   │   └── run_eval.py               # CLI eval runner
│   ├── Dockerfile
│   ├── railway.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx               # Claim submission form
│   │   │   ├── claims/[id]/page.tsx   # Decision trace viewer
│   │   │   ├── claims/page.tsx        # All claims list
│   │   │   └── eval/page.tsx          # Eval suite runner
│   │   ├── components/
│   │   │   ├── TraceViewer.tsx        # Shared agent trace accordion
│   │   │   └── ui/                    # shadcn/ui components
│   │   └── lib/
│   │       ├── api.ts                 # API client
│   │       └── types.ts               # TypeScript types
│   └── next.config.ts
└── README.md
```

---

## Deployment

### Backend → Railway

1. Create a new Railway project and connect this repository
2. Set the **root directory** to `backend/`
3. Railway will auto-detect the `Dockerfile`
4. Add environment variables in Railway dashboard:
   ```
   OPENAI_API_KEY=sk-...
   FRONTEND_URL=https://your-app.vercel.app
   ```
5. Railway exposes `$PORT` automatically — the Dockerfile and `railway.toml` handle it

### Frontend → Vercel

1. Import this repository on Vercel
2. Set the **root directory** to `frontend/`
3. Add environment variable in Vercel dashboard:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.railway.app
   ```
4. Deploy — Vercel auto-detects Next.js

---

## Deliverables

| # | Deliverable | Location |
|---|-------------|----------|
| 1 | Working system | This repo + deployed URLs above |
| 2 | Architecture document | `ARCHITECTURE.md` |
| 3 | Component contracts | `COMPONENT_CONTRACTS.md` |
| 4 | Eval report | `EVAL_REPORT.md` |
| 5 | Demo video | *(link to be added)* |

---

## Author

**Sudarshan Venkatesh**

- GitHub: [sudarshanvenkatesh13](https://github.com/sudarshanvenkatesh13)
- Email: sudarshan.venkateshv@gmail.com
