
from datetime import date
from pathlib import Path
import re
from typing import Any

from app.analysis.extraction import (
    ExtractionRequest,
    ExtractionResult,
)
from app.analysis.metrics import get_xbrl_metric_label
from app.analysis.schemas import (
    FinancialEvidence,
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
)
from app.sec_extractor import (
    load_sec_report,
    extract_filing_metadata,
    extract_contexts,
    extract_numeric_facts,
    extract_units,
    enrich_facts_with_contexts,
    normalize_numeric_value,
)


class SECXBRLExtractor:
    """Extract standardized financial metrics from SEC XBRL reports."""

    source_type = "sec_xbrl"
    supported_extensions = (".html", ".htm", ".xhtml", ".xml")

    def extract(
        self,
        request: ExtractionRequest,
    ) -> ExtractionResult:
        file_path = Path(request.file_path)

        if file_path.suffix.lower() not in self.supported_extensions:
            raise ValueError(
                f"Unsupported SEC report extension: {file_path.suffix}"
            )

        if request.expected_cik is not None:
            if not re.fullmatch(r"\d{10}", request.expected_cik):
                raise ValueError(
                    "expected_cik must contain exactly 10 digits."
                )

        soup = load_sec_report(file_path)

        # Extract filing-level fiscal metadata.
        filing_metadata = extract_filing_metadata(soup)

        contexts = extract_contexts(soup)
        facts = extract_numeric_facts(soup)
        units = extract_units(soup)

        enriched_facts = enrich_facts_with_contexts(
            facts,
            contexts,
            units,
        )

        metrics: list[FinancialMetric] = []
        warnings: list[str] = []

        skipped = {
            "missing_context": 0,
            "invalid_value": 0,
            "invalid_period": 0,
            "cik_mismatch": 0,
            "period_mismatch": 0,
            "missing_unit": 0,
        }

        for fact in enriched_facts:
            context = fact.get("context")

            if not isinstance(context, dict):
                skipped["missing_context"] += 1
                continue

            if request.expected_cik is not None:
                if (
                    context.get("identifier") != request.expected_cik
                    or context.get("identifier_scheme")
                    != "http://www.sec.gov/CIK"
                ):
                    skipped["cik_mismatch"] += 1
                    continue

            period = self._build_period(
                context=context,
                filing_metadata=filing_metadata,
            )

            if period is None:
                skipped["invalid_period"] += 1
                continue

            if not self._matches_requested_period(
                period,
                request.start_date,
                request.end_date,
            ):
                skipped["period_mismatch"] += 1
                continue

            value = normalize_numeric_value(fact)

            if value is None:
                skipped["invalid_value"] += 1
                continue

            unit_measures = fact.get("unit_measures")

            if not isinstance(unit_measures, list) or not unit_measures:
                skipped["missing_unit"] += 1
                continue

            unit = self._format_unit(unit_measures)
            currency = self._extract_currency(unit_measures)

            concept = fact.get("name")

            if not isinstance(concept, str) or not concept.strip():
                warnings.append(
                    "Skipped a numeric fact with no XBRL concept name."
                )
                continue

            metric_name = get_xbrl_metric_label(concept)

            dimensions = self._build_dimensions(
                context.get("dimensions", [])
            )

            fact_id = fact.get("fact_id")
            context_ref = fact.get("context_ref")

            metric = FinancialMetric(
                company=request.company,
                metric=metric_name,
                value=value,
                unit=unit,
                currency=currency,
                period=period,
                source=SourceProvenance(
                    source_type=self.source_type,
                    source_document_id=request.source_document_id,
                    filename=file_path.name,
                    fact_id=fact_id,
                    context_ref=context_ref,
                    source_reference=concept,
                ),
                evidence=FinancialEvidence(
                    text=str(fact.get("raw_value", "")),
                    original_label=concept,
                    extraction_method="SEC Inline XBRL numeric fact",
                    metadata={
                        "scale": fact.get("scale"),
                        "sign": fact.get("sign"),
                        "decimals": fact.get("decimals"),
                        "format": fact.get("format"),
                        "unit_ref": fact.get("unit_ref"),
                        "unit_measures": unit_measures,
                        "context_ref": context_ref,
                        "filing_metadata": filing_metadata,
                    },
                ),
                dimensions=dimensions,
            )

            metrics.append(metric)

        for reason, count in skipped.items():
            if count:
                warnings.append(
                    f"Skipped {count} fact(s): {reason.replace('_', ' ')}."
                )

        if not metrics:
            warnings.append(
                "No valid numeric financial metrics were extracted."
            )

        return ExtractionResult(
            source_type=self.source_type,
            filename=file_path.name,
            metrics=metrics,
            warnings=warnings,
            metadata={
                "company": request.company,
                "expected_cik": request.expected_cik,
                "filing_metadata": filing_metadata,
                "source_fact_count": len(facts),
                "enriched_fact_count": len(enriched_facts),
                "extracted_metric_count": len(metrics),
                "skipped_fact_counts": skipped,
                "context_count": len(contexts),
                "unit_count": len(units),
            },
        )

    @staticmethod
    def _build_period(
        context: dict[str, Any],
        filing_metadata: dict[str, Any],
    ) -> ReportingPeriod | None:
        period_type = context.get("period_type")

        try:
            if period_type == "duration":
                start_date = date.fromisoformat(
                    context["start_date"]
                )
                end_date = date.fromisoformat(
                    context["end_date"]
                )

                if start_date >= end_date:
                    return None

                fiscal_year, fiscal_period, period_scope = (
                    SECXBRLExtractor._classify_duration_period(
                        start_date=start_date,
                        end_date=end_date,
                        filing_metadata=filing_metadata,
                    )
                )

                return ReportingPeriod(
                    label=(
                        f"{start_date.isoformat()} to "
                        f"{end_date.isoformat()}"
                    ),
                    period_type="duration",
                    start_date=start_date,
                    end_date=end_date,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    period_scope=period_scope,
                )

            if period_type == "instant":
                instant_date = date.fromisoformat(
                    context["instant"]
                )

                return ReportingPeriod(
                    label=instant_date.isoformat(),
                    period_type="instant",
                    instant_date=instant_date,
                )

            if period_type == "unknown":
                return ReportingPeriod(
                    period_type="unknown",
                )

        except (KeyError, TypeError, ValueError):
            return None

        return None

    @staticmethod
    def _classify_duration_period(
        start_date: date,
        end_date: date,
        filing_metadata: dict[str, Any],
    ) -> tuple[int | None, str | None, str]:
        """
        Classify an XBRL duration using filing metadata
        and approximate duration ranges.

        Returns:
            fiscal_year, fiscal_period, period_scope
        """

        fiscal_year_focus = filing_metadata.get(
            "fiscal_year_focus"
        )
        fiscal_period_focus = filing_metadata.get(
            "fiscal_period_focus"
        )
        document_period_end_date = filing_metadata.get(
            "document_period_end_date"
        )

        if (
            not isinstance(fiscal_year_focus, int)
            or fiscal_period_focus not in {"Q1", "Q2", "Q3", "FY"}
            or not document_period_end_date
        ):
            return None, None, "unknown"

        try:
            filing_end_date = date.fromisoformat(
                document_period_end_date
            )
        except (TypeError, ValueError):
            return None, None, "unknown"

        if end_date > filing_end_date:
            return None, None, "unknown"

        # Approximate comparative fiscal year.
        fiscal_year = (
            fiscal_year_focus
            + end_date.year
            - filing_end_date.year
        )

        if not 1900 <= fiscal_year <= 2200:
            return None, None, "unknown"

        duration_days = (end_date - start_date).days

        # Annual duration.
        if 330 <= duration_days <= 380:
            return fiscal_year, "FY", "annual"

        # Q2 year-to-date duration.
        if 150 <= duration_days <= 200:
            if fiscal_period_focus != "Q2":
                return None, None, "unknown"

            return fiscal_year, "Q2", "ytd"

        # Q3 year-to-date duration.
        if 230 <= duration_days <= 300:
            if fiscal_period_focus != "Q3":
                return None, None, "unknown"

            return fiscal_year, "Q3", "ytd"

        # Standalone quarterly duration.
        if 70 <= duration_days <= 110:
            if fiscal_period_focus not in {"Q1", "Q2", "Q3"}:
                return None, None, "unknown"

            return fiscal_year, fiscal_period_focus, "standalone"

        return None, None, "unknown"

    @staticmethod
    def _matches_requested_period(
        period: ReportingPeriod,
        start_date: date | None,
        end_date: date | None,
    ) -> bool:
        if start_date is None and end_date is None:
            return True

        if period.period_type != "duration":
            return False

        return (
            period.start_date == start_date
            and period.end_date == end_date
        )

    @staticmethod
    def _format_unit(unit_measures: list[str]) -> str:
        return " * ".join(
            str(measure).strip()
            for measure in unit_measures
        )

    @staticmethod
    def _extract_currency(
        unit_measures: list[str],
    ) -> str | None:
        currencies = set()

        for measure in unit_measures:
            match = re.fullmatch(
                r"iso4217:([A-Z]{3})",
                str(measure).strip(),
            )

            if match:
                currencies.add(match.group(1))

        if len(currencies) == 1:
            return currencies.pop()

        return None

    @staticmethod
    def _build_dimensions(
        raw_dimensions: Any,
    ) -> dict[str, str]:
        if not isinstance(raw_dimensions, list):
            return {}

        dimensions: dict[str, str] = {}

        for dimension in raw_dimensions:
            if not isinstance(dimension, dict):
                continue

            axis = dimension.get("axis")
            member = dimension.get("member")

            if not isinstance(axis, str) or not isinstance(member, str):
                continue

            axis = axis.strip()
            member = member.strip()

            if axis and member:
                dimensions[axis] = member

        return dimensions
