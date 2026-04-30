"""Agent 2: Extracts structured data from each document via GPT-4o Vision."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def run_document_extraction(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder — will be implemented in the next phase.

    For each classified document:
    - Calls LLMService.extract_document(image_base64, document_type)
    - Stores DocumentExtractionResult per file
    - Aggregates extracted patient name, date, amounts for downstream validation
    """
    logger.info("Agent 2 (DocumentExtraction): placeholder invoked")
    from models.document import DocumentExtractionResult, DocumentType

    doc_verification_result = state.get("doc_verification_result")
    documents = state.get("documents", [])

    extraction_results = []
    for doc in documents:
        extraction_results.append(
            DocumentExtractionResult(
                file_id=doc.file_id,
                document_type=DocumentType.PRESCRIPTION,
                confidence=0.85,
                raw_text=None,
            )
        )

    return {**state, "extraction_results": extraction_results}
