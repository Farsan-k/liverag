
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Any
from decimal import Decimal, InvalidOperation
from datetime import date
import re

def load_sec_report(file_path: str | Path) -> BeautifulSoup:
    """
    Load an SEC 10-K XHTML/iXBRL report.

    Args:
        file_path: Path to the SEC report.

    Returns:
        Parsed BeautifulSoup XML document.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"SEC report not found: {path}")

    if not path.is_file():
        raise ValueError(f"Expected a file, got: {path}")

    content = path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    return BeautifulSoup(content, "xml")






def extract_filing_metadata(
    soup: BeautifulSoup,
) -> dict[str, Any]:
    """
    Extract filing-level fiscal metadata from SEC XBRL reports.

    Reads DocumentType, DocumentFiscalYearFocus,
    DocumentFiscalPeriodFocus and DocumentPeriodEndDate.
    """

    def get_tag_value(local_name: str) -> str | None:
        tag = soup.find(
            lambda element: (
                element.name
                and element.name.lower().split(":")[-1]
                == local_name.lower()
            )
        )

        if tag is None:
            return None

        value = tag.get_text(" ", strip=True)

        return value or None

    document_type = get_tag_value("DocumentType")
    fiscal_year_raw = get_tag_value("DocumentFiscalYearFocus")
    fiscal_period = get_tag_value("DocumentFiscalPeriodFocus")
    period_end_date = get_tag_value("DocumentPeriodEndDate")

    fiscal_year = None

    if fiscal_year_raw:
        try:
            fiscal_year = int(fiscal_year_raw)

            if not 1900 <= fiscal_year <= 2200:
                fiscal_year = None

        except (TypeError, ValueError):
            fiscal_year = None

    if fiscal_period:
        fiscal_period = fiscal_period.upper().strip()

        if fiscal_period not in {"Q1", "Q2", "Q3", "FY"}:
            fiscal_period = None

    if period_end_date:
        try:
            period_end_date = date.fromisoformat(
                period_end_date
            ).isoformat()
        except ValueError:
            period_end_date = None

    return {
        "document_type": document_type,
        "fiscal_year_focus": fiscal_year,
        "fiscal_period_focus": fiscal_period,
        "document_period_end_date": period_end_date,
    }






def extract_contexts(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    """
    Extract XBRL contexts, including entity identifiers,
    reporting periods, and dimensional information.
    """

    contexts = {}

    for context in soup.find_all(
        lambda tag: tag.name and tag.name.lower().endswith("context")
    ):
        context_id = context.get("id")

        if not context_id:
            continue

        identifier_tag = context.find(
            lambda tag: tag.name and tag.name.lower().endswith("identifier")
        )

        identifier = None
        identifier_scheme = None

        if identifier_tag:
            identifier = identifier_tag.get_text(" ", strip=True)
            identifier_scheme = identifier_tag.get("scheme")

        start_date_tag = context.find(
            lambda tag: tag.name and tag.name.lower().endswith("startdate")
        )

        end_date_tag = context.find(
            lambda tag: tag.name and tag.name.lower().endswith("enddate")
        )

        instant_tag = context.find(
            lambda tag: tag.name and tag.name.lower().endswith("instant")
        )

        start_date = (
            start_date_tag.get_text(" ", strip=True)
            if start_date_tag else None
        )

        end_date = (
            end_date_tag.get_text(" ", strip=True)
            if end_date_tag else None
        )

        instant = (
            instant_tag.get_text(" ", strip=True)
            if instant_tag else None
        )

        if instant:
            period_type = "instant"
        elif start_date and end_date:
            period_type = "duration"
        else:
            period_type = "unknown"

        dimensions = []

        for child in context.find_all(
            lambda tag: tag.name
            and (
                tag.name.lower().endswith("explicitmember")
                or tag.name.lower().endswith("typedmember")
            )
        ):
            is_typed = child.name.lower().endswith("typedmember")

            dimensions.append({
                "type": "typed" if is_typed else "explicit",
                "axis": child.get("dimension"),
                "member": child.get_text(" ", strip=True),
            })

        contexts[context_id] = {
            "context_id": context_id,
            "identifier": identifier,
            "identifier_scheme": identifier_scheme,
            "period_type": period_type,
            "start_date": start_date,
            "end_date": end_date,
            "instant": instant,
            "dimensions": dimensions,
        }

    return contexts





def extract_numeric_facts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """
    Extract numeric XBRL facts from both:
    1. Inline XBRL (ix:nonFraction)
    2. Standard XBRL instance documents

    Preserves original values and fact metadata.
    """

    facts: list[dict[str, Any]] = []

    for tag in soup.find_all(True):
        attributes = {
            key.lower(): value
            for key, value in tag.attrs.items()
        }

        tag_name = (tag.name or "").lower()

        is_inline_numeric = tag_name.endswith("nonfraction")

        is_standard_numeric = (
            bool(attributes.get("contextref"))
            and bool(attributes.get("unitref"))
            and not is_inline_numeric
        )

        if not is_inline_numeric and not is_standard_numeric:
            continue

        raw_value = tag.get_text("", strip=True)

        if not raw_value:
            continue

        # Inline XBRL uses the name attribute.
        # Standard XBRL uses the element's qualified tag name.
        concept_name = (
            attributes.get("name")
            if is_inline_numeric
            else tag.name
        )

        if not concept_name:
            continue

        fact = {
            "name": str(concept_name),
            "context_ref": attributes.get("contextref"),
            "unit_ref": attributes.get("unitref"),
            "scale": attributes.get("scale"),
            "sign": attributes.get("sign"),
            "decimals": attributes.get("decimals"),
            "format": attributes.get("format"),
            "fact_id": attributes.get("id"),
            "raw_value": raw_value,
        }

        facts.append(fact)

    return facts




def enrich_facts_with_contexts(
    facts: list[dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
    units: dict[str, list[str]]
) -> list[dict[str, Any]]:

    enriched_facts = []

    for fact in facts:
        enriched_fact = fact.copy()

        enriched_fact["context"] = contexts.get(
            fact.get("context_ref")
        )

        enriched_fact["unit_measures"] = units.get(
            fact.get("unit_ref"),
            []
        )

        enriched_facts.append(enriched_fact)

    return enriched_facts






def normalize_numeric_value(fact: dict[str, Any]) -> Decimal | None:
    """
    Normalize an Inline XBRL numeric fact using Decimal
    to preserve financial precision.

    Supported transformations:
    - ixt:num-dot-decimal
    - ixt:fixed-zero
    - ixt-sec:numwordsen

    Also supports numeric values without an explicit format.

    Returns None for missing, invalid, or unsupported values.
    """

    format_name = fact.get("format")
    raw_value = fact.get("raw_value")

    try:
        scale = int(fact.get("scale") or 0)
        sign = fact.get("sign")

        # Prevent unreasonable scale values.
        if not -100 <= scale <= 100:
            return None

        # Validate the XBRL sign attribute.
        if sign not in (None, "", "+", "-"):
            return None

        # Validate raw value.
        if raw_value is None:
            return None

        raw_value = str(raw_value).strip()

        if not raw_value:
            return None

        # Handle fixed-zero transformation.
        if format_name == "ixt:fixed-zero":
            if raw_value in {"-", "—", "–"}:
                return Decimal("0")

            return None

        number_words = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }

        if format_name == "ixt-sec:numwordsen":
            value = Decimal(number_words[raw_value.lower()])

        elif format_name in (None, "ixt:num-dot-decimal"):

            # Remove whitespace around the number.
            cleaned_value = "".join(raw_value.split())

            # Detect negative numbers represented using parentheses.
            is_parenthesized = (
                cleaned_value.startswith("(")
                and cleaned_value.endswith(")")
            )

            if is_parenthesized:
                cleaned_value = cleaned_value[1:-1]

                # Reject conflicting sign notation.
                if cleaned_value.startswith(("+", "-")):
                    return None

            # Validate standard decimal notation and comma grouping.
            number_pattern = (
                r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"
            )

            if not re.fullmatch(number_pattern, cleaned_value):
                return None

            # Remove validated thousands separators.
            value = Decimal(cleaned_value.replace(",", ""))

            if is_parenthesized:
                value = -abs(value)

        else:
            return None

        # Apply XBRL scale exactly without float conversion or rounding.
        sign_bit, digits, exponent = value.as_tuple()
        value = Decimal((sign_bit, digits, exponent + scale))

        # Apply the XBRL sign attribute.
        if sign == "-":
            value = -abs(value)

        if not value.is_finite():
            return None

        return value

    except (
        ValueError,
        TypeError,
        KeyError,
        InvalidOperation,
        OverflowError,
    ):
        return None




def validate_revenue_breakdown(
    product_revenue: Decimal,
    services_revenue: Decimal,
    consolidated_revenue: Decimal,
    tolerance: Decimal = Decimal("0.01")
) -> dict[str, Any]:

    # Validate input types.
    inputs = {
        "product_revenue": product_revenue,
        "services_revenue": services_revenue,
        "consolidated_revenue": consolidated_revenue,
        "tolerance": tolerance,
    }

    for name, value in inputs.items():
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be a Decimal value.")

        if not value.is_finite():
            raise ValueError(f"{name} must be a finite Decimal value.")

    # Tolerance cannot be negative.
    if tolerance < Decimal("0"):
        raise ValueError("Tolerance cannot be negative.")

    # Calculate revenue reconciliation.
    calculated_total = product_revenue + services_revenue

    difference = abs(calculated_total - consolidated_revenue)

    return {
        "product_revenue": product_revenue,
        "services_revenue": services_revenue,
        "calculated_total": calculated_total,
        "consolidated_revenue": consolidated_revenue,
        "difference": difference,
        "is_valid": difference <= tolerance
    }












def extract_revenue_breakdown(
    enriched_facts: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    revenue_concept: str = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    unit: str = "USD",
    *,
    expected_cik: str,
) -> dict[str, Any]:
    """
    Extract product, services, and consolidated revenue from SEC Inline XBRL facts.

    Validates:
    - Input types and required values.
    - ISO reporting period dates and date order.
    - Company CIK and identifier scheme.
    - Duration context.
    - Currency/unit.
    - Product or service dimensions.
    - Duplicate and conflicting facts.
    - Product + services reconciliation against consolidated revenue.
    """

    # 1. Validate enriched facts.
    if not isinstance(enriched_facts, list):
        raise TypeError("enriched_facts must be a list.")

    # 2. Validate reporting dates.
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        raise TypeError("start_date and end_date must be strings.")

    try:
        parsed_start_date = date.fromisoformat(start_date)
        parsed_end_date = date.fromisoformat(end_date)
    except ValueError:
        raise ValueError("Dates must use valid ISO format: YYYY-MM-DD.")

    if (
        parsed_start_date.isoformat() != start_date
        or parsed_end_date.isoformat() != end_date
    ):
        raise ValueError("Dates must use ISO format: YYYY-MM-DD.")

    if parsed_start_date >= parsed_end_date:
        raise ValueError("start_date must be earlier than end_date.")

    # 3. Validate revenue concept.
    if not isinstance(revenue_concept, str):
        raise TypeError("revenue_concept must be a string.")

    if not revenue_concept.strip():
        raise ValueError("revenue_concept cannot be empty.")

    # 4. Validate currency/unit.
    if not isinstance(unit, str):
        raise TypeError("unit must be a string.")

    unit = unit.strip().upper()

    if not re.fullmatch(r"[A-Z]{3}", unit):
        raise ValueError("unit must be a three-letter currency code.")

    # 5. Validate expected CIK.
    if not isinstance(expected_cik, str):
        raise TypeError("expected_cik must be a string.")

    if not re.fullmatch(r"\d{10}", expected_cik):
        raise ValueError("expected_cik must contain exactly 10 digits.")

    # 6. Define expected XBRL dimensions.
    expected_axis = "srt:ProductOrServiceAxis"
    expected_measure = f"iso4217:{unit}"

    product_member = "us-gaap:ProductMember"

    service_members = {
        "us-gaap:ServiceMember",
        "us-gaap:ServiceOtherMember",
    }

    # 7. Store matching revenue candidates.
    candidates = {
        "product": [],
        "services": [],
        "consolidated": [],
    }

    # 8. Extract matching revenue facts.
    for fact in enriched_facts:

        context = fact.get("context")

        if not context:
            continue

        # Validate company identity.
        if context.get("identifier") != expected_cik:
            continue

        if context.get("identifier_scheme") != "http://www.sec.gov/CIK":
            continue

        # Only duration contexts are valid for revenue.
        if context.get("period_type") != "duration":
            continue

        # Match reporting period.
        if context.get("start_date") != start_date:
            continue

        if context.get("end_date") != end_date:
            continue

        # Match revenue concept.
        if fact.get("name") != revenue_concept:
            continue

        # Match currency.
        unit_measures = fact.get("unit_measures", [])

        if not isinstance(unit_measures, list):
            continue

        if expected_measure not in unit_measures:
            continue

        # Validate dimensions.
        dimensions = context.get("dimensions", [])

        if not isinstance(dimensions, list):
            continue

        if not all(isinstance(dimension, dict) for dimension in dimensions):
            continue

        category = None

        # Consolidated revenue must not contain dimensions.
        if len(dimensions) == 0:
            category = "consolidated"

        # Product and services must have exactly one expected dimension.
        elif len(dimensions) == 1:

            dimension = dimensions[0]

            if dimension.get("axis") != expected_axis:
                continue

            member = dimension.get("member")

            if member == product_member:
                category = "product"

            elif member in service_members:
                category = "services"

        if category is None:
            continue

        # Normalize numeric XBRL value.
        value = normalize_numeric_value(fact)

        if value is None:
            continue

        candidates[category].append(value)

    # 9. Ensure every category has at least one valid fact.
    for category, values in candidates.items():

        if not values:
            raise ValueError(
                f"Missing {category} revenue for the requested "
                f"company, reporting period, and currency."
            )

    # 10. Detect conflicting values while allowing identical duplicates.
    unique_values = {}

    for category, values in candidates.items():

        unique = set(values)

        if len(unique) > 1:
            raise ValueError(
                f"Conflicting {category} revenue facts found: "
                f"{sorted(unique)}"
            )

        unique_values[category] = unique.pop()

    # 11. Extract final revenue values.
    product_revenue = unique_values["product"]
    services_revenue = unique_values["services"]
    consolidated_revenue = unique_values["consolidated"]

    # 12. Validate revenue reconciliation.
    validation = validate_revenue_breakdown(
        product_revenue=product_revenue,
        services_revenue=services_revenue,
        consolidated_revenue=consolidated_revenue,
    )

    # 13. Return extracted financial data.
    return {
        "product_revenue": product_revenue,
        "services_revenue": services_revenue,
        "consolidated_revenue": consolidated_revenue,
        "difference": validation["difference"],
        "is_valid": validation["is_valid"],
        "source_fact_counts": {
            category: len(values)
            for category, values in candidates.items()
        },
        "unique_fact_counts": {
            category: len(set(values))
            for category, values in candidates.items()
        },
        "reporting_period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "unit": unit,
        "unit_measure": expected_measure,
        "expected_cik": expected_cik,
    }










def extract_units(soup: BeautifulSoup) -> dict[str, list[str]]:
    """
    Extract SEC XBRL unit definitions.

    Example:
    {
        "U_USD": ["iso4217:USD"],
        "usd": ["iso4217:USD"]
    }
    """

    units = {}

    for unit in soup.find_all(
        lambda tag: tag.name
        and tag.name.lower().endswith("unit")
    ):
        unit_id = unit.get("id")

        if not unit_id:
            continue

        measures = [
            measure.get_text(" ", strip=True)
            for measure in unit.find_all(
                lambda tag: tag.name
                and tag.name.lower().endswith("measure")
            )
        ]

        units[unit_id] = measures

    return units
