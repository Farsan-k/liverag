
from pathlib import Path
from datetime import date

from app.crud import (
    get_financial_document,
    update_financial_document_extraction_status,
    create_financial_metrics,
)
from app.analysis.extraction import (
    ExtractionRequest,
    ExtractionResult,
)
from app.analysis.registry import create_default_registry
from app.storage.factory import get_storage_service


def extract_financial_document(
    financial_document_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ExtractionResult:
    """
    Extract structured financial metrics from a stored document.

    Workflow:
    1. Retrieve financial document metadata from PostgreSQL.
    2. Validate the stored file.
    3. Mark extraction as processing.
    4. Select the appropriate extractor.
    5. Execute extraction.
    6. Persist extracted financial metrics.
    7. Mark extraction as completed.

    If extraction or persistence fails, the status is updated
    to failed and the exception is propagated.
    """

    # Step 1: Retrieve document metadata.
    document = get_financial_document(financial_document_id)

    if document is None:
        raise ValueError(
            f"Financial document {financial_document_id} not found."
        )

    # Step 2: Validate stored file.
    storage = get_storage_service()
    storage_path = Path(document["storage_path"])

    if not storage.file_exists(str(storage_path)):
        update_financial_document_extraction_status(
            financial_document_id,
            "failed",
        )

        raise FileNotFoundError(
            f"Stored financial file not found: {storage_path}"
        )

    # Step 3: Mark extraction as processing.
    update_financial_document_extraction_status(
        financial_document_id,
        "processing",
    )

    try:
        # Step 4: Initialize extractor registry.
        registry = create_default_registry()

        # Step 5: Build extraction request.
        request = ExtractionRequest(
            file_path=storage_path,
            company=document["company"],
            source_document_id=financial_document_id,
            expected_cik=document["expected_cik"],
            start_date=start_date,
            end_date=end_date,
        )

        # Step 6: Execute extraction.
        result = registry.extract(request)

        # Step 7: Persist extracted metrics.
        create_financial_metrics(
            source_document_id=financial_document_id,
            metrics=result.metrics,
        )

        # Step 8: Mark extraction as completed.
        update_financial_document_extraction_status(
            financial_document_id,
            "completed",
        )

        return result

    except Exception:
        # Mark extraction as failed if extraction or
        # metric persistence fails.
        update_financial_document_extraction_status(
            financial_document_id,
            "failed",
        )

        raise
