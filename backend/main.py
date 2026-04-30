from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.claim import ClaimSubmission, ClaimResponse
from orchestrator.pipeline import ClaimsPipeline
from services.policy_loader import PolicyLoader

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Plum Claims Processor",
    description="Multi-agent AI health insurance claims processing system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup state
# ---------------------------------------------------------------------------
claims_store: Dict[str, ClaimResponse] = {}
policy_loader: PolicyLoader = None  # type: ignore[assignment]
pipeline: ClaimsPipeline = None  # type: ignore[assignment]


@app.on_event("startup")
async def startup_event() -> None:
    global policy_loader, pipeline
    logger.info("Starting up Plum Claims Processor...")
    policy_loader = PolicyLoader(settings.POLICY_FILE_PATH)
    pipeline = ClaimsPipeline()
    logger.info("Startup complete. Policy loaded, pipeline ready.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "plum-claims-processor"}


@app.post("/api/claims/submit", response_model=ClaimResponse, tags=["Claims"])
async def submit_claim(submission: ClaimSubmission) -> ClaimResponse:
    logger.info(
        "Claim submission received | member=%s | category=%s | amount=%.2f",
        submission.member_id,
        submission.claim_category.value,
        submission.claimed_amount,
    )
    try:
        result = await pipeline.process(submission)
        claims_store[result.claim_id] = result
        logger.info("Claim %s processed | decision=%s", result.claim_id, result.decision)
        return result
    except Exception as exc:
        logger.exception("Unhandled error processing claim: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {exc}") from exc


@app.get("/api/claims/{claim_id}", response_model=ClaimResponse, tags=["Claims"])
async def get_claim(claim_id: str) -> ClaimResponse:
    if claim_id not in claims_store:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return claims_store[claim_id]


@app.get("/api/claims", tags=["Claims"])
async def list_claims() -> List[Dict[str, Any]]:
    summary = []
    for claim_id, claim in claims_store.items():
        summary.append(
            {
                "claim_id": claim_id,
                "status": claim.status,
                "decision": claim.decision,
                "approved_amount": claim.approved_amount,
                "confidence_score": claim.confidence_score,
            }
        )
    return summary


@app.get("/api/policy/members", tags=["Policy"])
async def get_members() -> List[Dict[str, Any]]:
    try:
        members = policy_loader.get_all_members()
        return [m.model_dump() for m in members]
    except Exception as exc:
        logger.exception("Failed to load members: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/policy/categories", tags=["Policy"])
async def get_categories() -> Dict[str, Any]:
    try:
        all_cats = policy_loader.get_all_categories()
        result: Dict[str, Any] = {}
        for cat_name, cat_config in all_cats.items():
            doc_reqs = policy_loader.get_document_requirements(cat_name)
            result[cat_name] = {
                "config": cat_config,
                "document_requirements": doc_reqs,
            }
        return result
    except Exception as exc:
        logger.exception("Failed to load categories: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
