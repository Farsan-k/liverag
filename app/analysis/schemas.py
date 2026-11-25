
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


SourceType = Literal[
    "sec_xbrl",
    "pdf",
    "excel",
    "csv",
    "text",
]

PeriodType = Literal[
    "duration",
    "instant",
    "unknown",
]

FiscalPeriod = Literal[
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "FY",
]

PeriodScope = Literal[
    "standalone",
    "ytd",
    "annual",
    "unknown",
]


class ReportingPeriod(BaseModel):
    """Represents the reporting period associated with a financial metric."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    period_type: PeriodType = "unknown"

    start_date: date | None = None
    end_date: date | None = None
    instant_date: date | None = None

    # Fiscal reporting identity
    fiscal_year: int | None = Field(
        default=None,
        ge=1900,
        le=2200,
    )
    fiscal_period: FiscalPeriod | None = None

    # Distinguishes standalone quarterly values from cumulative values.
    period_scope: PeriodScope = "unknown"

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_type == "duration":
            if self.start_date is None or self.end_date is None:
                raise ValueError(
                    "Duration periods require start_date and end_date."
                )

            if self.start_date > self.end_date:
                raise ValueError(
                    "start_date cannot be after end_date."
                )

            if self.instant_date is not None:
                raise ValueError(
                    "Duration periods cannot have an instant_date."
                )

        elif self.period_type == "instant":
            if self.instant_date is None:
                raise ValueError(
                    "Instant periods require instant_date."
                )

            if self.start_date is not None or self.end_date is not None:
                raise ValueError(
                    "Instant periods cannot have start_date or end_date."
                )

            if self.period_scope != "unknown":
                raise ValueError(
                    "Instant periods must have period_scope='unknown'."
                )

        if (self.fiscal_year is None) != (self.fiscal_period is None):
            raise ValueError(
                "fiscal_year and fiscal_period must be provided together."
            )

        if self.period_scope != "unknown":
            if self.period_type != "duration":
                raise ValueError(
                    "A known period_scope requires a duration period."
                )

            if self.fiscal_year is None or self.fiscal_period is None:
                raise ValueError(
                    "A known period_scope requires fiscal_year "
                    "and fiscal_period."
                )

        if self.period_scope == "annual":
            if self.fiscal_period != "FY":
                raise ValueError(
                    "Annual periods must use fiscal_period='FY'."
                )

        if self.period_scope in {"standalone", "ytd"}:
            if self.fiscal_period == "FY":
                raise ValueError(
                    "Standalone and YTD periods must use a quarterly "
                    "fiscal_period."
                )

        return self


class SourceProvenance(BaseModel):
    """Identifies exactly where an extracted financial value originated."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType

    source_document_id: int | str | None = None
    filename: str | None = None

    # PDF location
    page_number: int | None = Field(default=None, ge=1)

    # Excel location
    sheet_name: str | None = None
    cell_reference: str | None = None

    # CSV / tabular location
    row_number: int | None = Field(default=None, ge=1)

    # SEC XBRL location
    fact_id: str | None = None
    context_ref: str | None = None

    # Retrieval / chunk location
    chunk_id: str | None = None

    source_reference: str | None = None


class FinancialEvidence(BaseModel):
    """Stores the supporting evidence for an extracted financial metric."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    original_label: str | None = None
    extraction_method: str | None = None

    # Additional source-specific extraction details
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinancialMetric(BaseModel):
    """Normalized financial metric used by the analysis engine."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = None

    # Canonical metric name, e.g. Revenue, Net Income, EPS
    metric: str = Field(min_length=1)

    # Decimal preserves financial precision.
    value: Decimal

    # Generic unit supports monetary and non-monetary metrics.
    unit: str = Field(min_length=1)

    # Optional ISO-style currency code, e.g. USD, INR, EUR.
    currency: str | None = None

    period: ReportingPeriod = Field(
        default_factory=ReportingPeriod
    )

    source: SourceProvenance

    evidence: FinancialEvidence = Field(
        default_factory=FinancialEvidence
    )

    # Examples: {"segment": "iPhone"}
    dimensions: dict[str, str] = Field(default_factory=dict)

    # Confidence must come from the extraction process.
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    @field_validator("metric", "unit")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty.")

        return value

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError(
                "Financial metric value must be finite."
            )

        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip().upper()

        if not value:
            raise ValueError("Currency cannot be empty.")

        return value
