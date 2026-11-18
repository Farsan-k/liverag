from pathlib import Path
from decimal import Decimal

import pytest

from app.sec_extractor import (
    load_sec_report,
    extract_contexts,
    extract_numeric_facts,
    extract_units,
    enrich_facts_with_contexts,
    extract_revenue_breakdown,
    normalize_numeric_value,
    validate_revenue_breakdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"



def extract_report_revenue(
    filename: str,
    start_date: str,
    end_date: str,
    expected_cik: str,
) -> dict:
    """Load a local SEC report and extract its revenue breakdown."""

    report_path = RAW_DATA_DIR / filename

    soup = load_sec_report(report_path)

    contexts = extract_contexts(soup)
    facts = extract_numeric_facts(soup)
    units = extract_units(soup)

    enriched_facts = enrich_facts_with_contexts(
        facts,
        contexts,
        units,
    )

    return extract_revenue_breakdown(
        enriched_facts=enriched_facts,
        start_date=start_date,
        end_date=end_date,
        expected_cik=expected_cik,
    )


@pytest.mark.parametrize(
    "filename,start_date,end_date,expected_cik,expected_product,expected_services,expected_total",
    [
        (
            "aapl-20250927.html",
            "2024-09-29",
            "2025-09-27",
            "0000320193",
            Decimal("307003000000"),
            Decimal("109158000000"),
            Decimal("416161000000"),
        ),
        (
            "10-K.html",
            "2024-07-01",
            "2025-06-30",
            "0000789019",
            Decimal("63946000000"),
            Decimal("217778000000"),
            Decimal("281724000000"),
        ),
    ],
    ids=["apple-fy2025", "microsoft-fy2025"],
)
def test_sec_revenue_breakdown(
    filename,
    start_date,
    end_date,
    expected_cik,
    expected_product,
    expected_services,
    expected_total,
):
    result = extract_report_revenue(
        filename=filename,
        start_date=start_date,
        end_date=end_date,
        expected_cik=expected_cik,
    )

    assert result["product_revenue"] == expected_product
    assert result["services_revenue"] == expected_services
    assert result["consolidated_revenue"] == expected_total
    assert result["difference"] == Decimal("0")
    assert result["is_valid"] is True
    assert result["unit_measure"] == "iso4217:USD"
    assert result["expected_cik"] == expected_cik


@pytest.fixture
def valid_revenue_facts():
    """Create synthetic, valid FY2025 revenue facts."""

    reporting_context = {
        "identifier": "0000789019",
        "identifier_scheme": "http://www.sec.gov/CIK",
        "period_type": "duration",
        "start_date": "2024-07-01",
        "end_date": "2025-06-30",
        "dimensions": [],
    }

    product_context = {
        **reporting_context,
        "dimensions": [
            {
                "type": "explicit",
                "axis": "srt:ProductOrServiceAxis",
                "member": "us-gaap:ProductMember",
            }
        ],
    }

    services_context = {
        **reporting_context,
        "dimensions": [
            {
                "type": "explicit",
                "axis": "srt:ProductOrServiceAxis",
                "member": "us-gaap:ServiceOtherMember",
            }
        ],
    }

    def make_fact(context, value):
        return {
            "name": (
                "us-gaap:"
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ),
            "context": context,
            "unit_measures": ["iso4217:USD"],
            "raw_value": str(value),
            "scale": "6",
            "sign": None,
        }

    return [
        make_fact(product_context, 63946),
        make_fact(services_context, 217778),
        make_fact(reporting_context, 281724),
    ]



def test_missing_product_revenue_raises_error(valid_revenue_facts):
    facts = valid_revenue_facts[1:]

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )


def test_missing_services_revenue_raises_error(valid_revenue_facts):
    facts = [
        valid_revenue_facts[0],
        valid_revenue_facts[2],
    ]

    with pytest.raises(ValueError, match="Missing services revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )


def test_missing_consolidated_revenue_raises_error(valid_revenue_facts):
    facts = valid_revenue_facts[:2]

    with pytest.raises(ValueError, match="Missing consolidated revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )



def test_enriched_facts_must_be_a_list():
    with pytest.raises(TypeError, match="enriched_facts must be a list"):
        extract_revenue_breakdown(
            enriched_facts="invalid",
            start_date="2024-07-01",
            end_date="2025-06-30",
            expected_cik="0000789019",
        )


@pytest.mark.parametrize(
    "start_date,end_date",
    [
        (2024, "2025-06-30"),
        ("2024-07-01", None),
    ],
)
def test_revenue_dates_must_be_strings(
    valid_revenue_facts,
    start_date,
    end_date,
):
    with pytest.raises(TypeError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date=start_date,
            end_date=end_date,
            expected_cik="0000789019",
        )




@pytest.mark.parametrize(
    "start_date,end_date",
    [
        ("01-07-2024", "2025-06-30"),
        ("2024-07-01", "30-06-2025"),
        ("invalid-date", "2025-06-30"),
    ],
)
def test_revenue_dates_must_use_iso_format(
    valid_revenue_facts,
    start_date,
    end_date,
):
    with pytest.raises(ValueError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date=start_date,
            end_date=end_date,
            expected_cik="0000789019",
        )



@pytest.mark.parametrize(
    "start_date,end_date",
    [
        ("2025-06-30", "2024-07-01"),
        ("2024-07-01", "2024-07-01"),
    ],
)
def test_revenue_start_date_must_be_before_end_date(
    valid_revenue_facts,
    start_date,
    end_date,
):
    with pytest.raises(ValueError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date=start_date,
            end_date=end_date,
            expected_cik="0000789019",
        )




def test_revenue_concept_must_not_be_empty(valid_revenue_facts):
    with pytest.raises(ValueError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date="2024-07-01",
            end_date="2025-06-30",
            revenue_concept="",
            expected_cik="0000789019",
        )




@pytest.mark.parametrize("revenue_concept", [None, 123])
def test_revenue_concept_must_be_a_string(
    valid_revenue_facts,
    revenue_concept,
):
    with pytest.raises(TypeError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date="2024-07-01",
            end_date="2025-06-30",
            revenue_concept=revenue_concept,
            expected_cik="0000789019",
        )



@pytest.mark.parametrize("unit", [None, 123])
def test_revenue_unit_must_be_a_string(
    valid_revenue_facts,
    unit,
):
    with pytest.raises(TypeError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date="2024-07-01",
            end_date="2025-06-30",
            revenue_concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            unit=unit,
            expected_cik="0000789019",
        )


@pytest.mark.parametrize(
    "unit",
    ["US", "USDD", "", "123", "USD$", "USD INR"],
)
def test_revenue_unit_must_be_three_letter_code(
    valid_revenue_facts,
    unit,
):
    with pytest.raises(ValueError):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date="2024-07-01",
            end_date="2025-06-30",
            revenue_concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            unit=unit,
            expected_cik="0000789019",
        )




@pytest.mark.parametrize(
    "expected_cik",
    [None, 1234567890, "123456789", "12345678901", "12345ABCDE", ""]
)
def test_expected_cik_must_be_valid(
    valid_revenue_facts,
    expected_cik
):
    with pytest.raises((TypeError, ValueError)):
        extract_revenue_breakdown(
            enriched_facts=valid_revenue_facts,
            start_date="2024-07-01",
            end_date="2025-06-30",
            revenue_concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            expected_cik=expected_cik,
        )





def test_conflicting_product_revenue_raises_error(valid_revenue_facts):
    conflicting_fact = valid_revenue_facts[0].copy()
    conflicting_fact["raw_value"] = "65000"

    facts = valid_revenue_facts + [conflicting_fact]

    with pytest.raises(ValueError, match="Conflicting product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )


def test_wrong_currency_raises_error(valid_revenue_facts):
    facts = []

    for fact in valid_revenue_facts:
        updated_fact = fact.copy()
        updated_fact["unit_measures"] = ["iso4217:EUR"]
        facts.append(updated_fact)

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )



def test_wrong_reporting_period_raises_error(valid_revenue_facts):
    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            valid_revenue_facts,
            "2023-07-01",
            "2024-06-30",
            expected_cik="0000789019",
        )




def test_revenue_reconciliation_failure():
    result = validate_revenue_breakdown(
        product_revenue=Decimal("100000000"),
        services_revenue=Decimal("50000000"),
        consolidated_revenue=Decimal("200000000"),
    )

    assert result["calculated_total"] == Decimal("150000000")
    assert result["difference"] == Decimal("50000000")
    assert result["is_valid"] is False





@pytest.mark.parametrize(
    "fact, expected",
    [
        ({"raw_value": "1250", "scale": "0"}, Decimal("1250")),
        ({"raw_value": "1,250", "scale": "0"}, Decimal("1250")),
        ({"raw_value": "1250.75", "scale": "0"}, Decimal("1250.75")),
        ({"raw_value": "1250", "scale": "6"}, Decimal("1250000000")),
        ({"raw_value": "1250", "scale": "0", "sign": "-"}, Decimal("-1250")),
        ({"raw_value": "(1250)", "scale": "0"}, Decimal("-1250")),
        ({"raw_value": " (1,250.50) ", "scale": "0"}, Decimal("-1250.50")),
        ({"raw_value": "1250", "scale": "0", "sign": "+"}, Decimal("1250")),
    ],
)
def test_normalize_numeric_value(fact, expected):
    assert normalize_numeric_value(fact) == expected


@pytest.mark.parametrize(
    "fact",
    [
        {"raw_value": None},
        {"raw_value": ""},
        {"raw_value": "abc"},
        {"raw_value": "1250", "scale": "invalid"},
        {"raw_value": "NaN"},
        {"raw_value": "Infinity"},
    ],
)
def test_normalize_invalid_numeric_value(fact):
    assert normalize_numeric_value(fact) is None

def test_normalize_numeric_value_returns_exact_decimal():
    fact = {
        "raw_value": "0.1",
        "scale": "0",
    }

    result = normalize_numeric_value(fact)

    # Verify the returned value is Decimal, not float.
    assert isinstance(result, Decimal)

    # Verify exact numerical precision.
    assert result == Decimal("0.1")

    # Verify the decimal representation.
    assert str(result) == "0.1"



@pytest.mark.parametrize(
    "raw_value, scale, expected",
    [
        ("123.45", "6", Decimal("123450000")),
        ("1234500", "-3", Decimal("1234.500")),
        ("0.123456789012345678901234567890123456789012345678901", "6",
         Decimal("123456.789012345678901234567890123456789012345678901")),
    ],
)
def test_normalize_numeric_value_applies_scale_exactly(
    raw_value, scale, expected
):
    result = normalize_numeric_value(
        {"raw_value": raw_value, "scale": scale}
    )

    assert result == expected
    assert isinstance(result, Decimal)


@pytest.mark.parametrize("scale", ["101", "-101"])
def test_normalize_numeric_value_rejects_out_of_range_scale(scale):
    result = normalize_numeric_value(
        {"raw_value": "1250", "scale": scale}
    )

    assert result is None


@pytest.mark.parametrize("sign", ["invalid", "negative", "++"])
def test_normalize_numeric_value_rejects_invalid_sign(sign):
    result = normalize_numeric_value(
        {"raw_value": "1250", "scale": "0", "sign": sign}
    )

    assert result is None


@pytest.mark.parametrize(
    "fact, expected",
    [
        (
            {
                "raw_value": "—",
                "format": "ixt:fixed-zero",
                "scale": "6",
            },
            Decimal("0"),
        ),
        (
            {
                "raw_value": "one",
                "format": "ixt-sec:numwordsen",
                "scale": "0",
            },
            Decimal("1"),
        ),
        (
            {
                "raw_value": "two",
                "format": "ixt-sec:numwordsen",
                "scale": "0",
            },
            Decimal("2"),
        ),
    ],
)
def test_normalize_sec_transformations(fact, expected):
    assert normalize_numeric_value(fact) == expected

@pytest.mark.parametrize(
    "raw_value",
    [None, "", "unexpected"],
)
def test_fixed_zero_rejects_invalid_raw_values(raw_value):
    fact = {
        "raw_value": raw_value,
        "format": "ixt:fixed-zero",
        "scale": "0",
    }

    assert normalize_numeric_value(fact) is None



@pytest.mark.parametrize("raw_value", ["no", "unknown"])
def test_normalize_invalid_number_words(raw_value):
    fact = {
        "raw_value": raw_value,
        "format": "ixt-sec:numwordsen",
    }

    assert normalize_numeric_value(fact) is None


def test_correct_company_cik_accepted(valid_revenue_facts):
    result = extract_revenue_breakdown(
        valid_revenue_facts,
        "2024-07-01",
        "2025-06-30",
        expected_cik="0000789019",
    )

    assert result["expected_cik"] == "0000789019"
    assert result["is_valid"] is True


def test_wrong_company_cik_rejected(valid_revenue_facts):
    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            valid_revenue_facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000320193",
        )


def test_wrong_identifier_scheme_rejected(valid_revenue_facts):
    facts = []

    for fact in valid_revenue_facts:
        updated_fact = fact.copy()
        updated_context = fact["context"].copy()
        updated_context["identifier_scheme"] = "https://example.com/CIK"
        updated_fact["context"] = updated_context
        facts.append(updated_fact)

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )



def test_instant_context_rejected(valid_revenue_facts):
    facts = []

    for fact in valid_revenue_facts:
        updated_fact = fact.copy()
        updated_context = fact["context"].copy()
        updated_context["period_type"] = "instant"
        updated_fact["context"] = updated_context
        facts.append(updated_fact)

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )





def test_unknown_period_type_rejected(valid_revenue_facts):
    facts = []

    for fact in valid_revenue_facts:
        updated_fact = fact.copy()
        updated_context = fact["context"].copy()
        updated_context["period_type"] = "unknown"
        updated_fact["context"] = updated_context
        facts.append(updated_fact)

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )


def test_missing_period_type_rejected(valid_revenue_facts):
    facts = []

    for fact in valid_revenue_facts:
        updated_fact = fact.copy()
        updated_context = fact["context"].copy()
        updated_context.pop("period_type")
        updated_fact["context"] = updated_context
        facts.append(updated_fact)

    with pytest.raises(ValueError, match="Missing product revenue"):
        extract_revenue_breakdown(
            facts,
            "2024-07-01",
            "2025-06-30",
            expected_cik="0000789019",
        )




def test_normalize_numeric_value_valid_comma_grouping():
    fact = {
        "raw_value": "1,234.56",
        "format": "ixt:num-dot-decimal",
    }

    assert normalize_numeric_value(fact) == Decimal("1234.56")


def test_normalize_numeric_value_rejects_invalid_comma_grouping():
    fact = {
        "raw_value": "12,34.56",
        "format": "ixt:num-dot-decimal",
    }

    assert normalize_numeric_value(fact) is None


def test_normalize_numeric_value_rejects_indian_comma_grouping():
    fact = {
        "raw_value": "1,23,456.78",
        "format": "ixt:num-dot-decimal",
    }

    assert normalize_numeric_value(fact) is None


def test_normalize_numeric_value_parenthesized_negative():
    fact = {
        "raw_value": "(1,234.56)",
        "format": "ixt:num-dot-decimal",
    }

    assert normalize_numeric_value(fact) == Decimal("-1234.56")




def test_revenue_breakdown_accepts_exact_tolerance():
    result = validate_revenue_breakdown(
        Decimal("100"),
        Decimal("50"),
        Decimal("149.99"),
        Decimal("0.01")
    )

    assert result["difference"] == Decimal("0.01")
    assert result["is_valid"] is True
