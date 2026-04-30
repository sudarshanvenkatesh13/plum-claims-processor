"""Agent 1: Verifies that the right document types were uploaded for the claim category."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def run_document_verification(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder — will be implemented in the next phase.

    Checks:
    - At least one document uploaded
    - Classifies each document via LLM
    - Verifies required document types are present for the claim category
    - Flags unreadable / poor quality documents
    """
    logger.info("Agent 1 (DocumentVerification): placeholder invoked")
    from models.document import DocVerificationResult, ClassifiedDocument, DocumentType, DocumentQuality

    documents = state.get("documents", [])
    category = state.get("claim_category", "")

    if not documents:
        result = DocVerificationResult(
            status="failed",
            missing_documents=["No documents uploaded"],
            error_message="No documents were provided with this claim.",
        )
        return {**state, "doc_verification_result": result, "pipeline_stop": True}

    # Mock classification for placeholder
    classified = [
        ClassifiedDocument(
            file_id=doc.file_id,
            file_name=doc.file_name,
            detected_type=DocumentType.PRESCRIPTION,
            quality=DocumentQuality.GOOD,
            confidence=0.9,
        )
        for doc in documents
    ]

    result = DocVerificationResult(
        status="passed",
        classified_documents=classified,
    )
    return {**state, "doc_verification_result": result}
