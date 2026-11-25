
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.analysis.schemas import FinancialMetric, SourceType


class ExtractionRequest(BaseModel):
    """Common input passed to a financial document extractor."""

    model_config = ConfigDict(extra="forbid")

    file_path: Path

    company: str | None = None
    source_document_id: int | str | None = None

    # SEC-specific identity information.
    expected_cik: str | None = None

    # Optional reporting period filter.
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_reporting_dates(self):
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError(
                "start_date and end_date must be provided together."
            )

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError(
                "start_date cannot be after end_date."
            )

        return self


class ExtractionResult(BaseModel):
    """Standardized output returned by every financial extractor."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    filename: str

    metrics: list[FinancialMetric] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_metric_sources(self):
        for metric in self.metrics:
            if metric.source.source_type != self.source_type:
                raise ValueError(
                    "Metric source_type must match extraction result source_type."
                )

            if (
                metric.source.filename is not None
                and metric.source.filename != self.filename
            ):
                raise ValueError(
                    "Metric filename must match extraction result filename."
                )

        return self


class FinancialDataExtractor(Protocol):
    """
    Common interface for SEC XBRL, PDF and future extractors.

    Every implementation must convert its source document
    into standardized FinancialMetric objects.
    """

    source_type: SourceType

    supported_extensions: tuple[str, ...]

    def extract(
        self,
        request: ExtractionRequest,
    ) -> ExtractionResult:
        """
        Extract financial metrics from a source document.

        Raises:
            FileNotFoundError: If the document does not exist.
            ValueError: If the document cannot be processed.
        """
        ...
