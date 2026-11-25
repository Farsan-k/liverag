
import re
from typing import Final


# Canonical metric names and their explicitly supported aliases.
# Avoid broad aliases that could map unrelated financial concepts.
METRIC_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "Revenue": (
        "revenue",
        "revenues",
        "total revenue",
        "net revenue",
        "total revenues",
        "net sales",
        "sales revenue",
    ),
    "Net Income": (
        "net income",
        "net profit",
        "profit after tax",
        "profit for the year",
        "profit for the period",
    ),
    "Gross Profit": (
        "gross profit",
        "gross income",
    ),
    "Operating Income": (
        "operating income",
        "income from operations",
        "operating profit",
        "profit from operations",
    ),
    "Operating Expenses": (
        "operating expenses",
        "total operating expenses",
    ),
    "Cost of Revenue": (
        "cost of revenue",
        "cost of revenues",
        "cost of sales",
        "cost of goods sold",
        "cogs",
    ),
    "Earnings Per Share": (
        "earnings per share",
        "basic earnings per share",
        "diluted earnings per share",
        "eps",
    ),
    "Operating Cash Flow": (
        "operating cash flow",
        "cash flow from operating activities",
        "net cash provided by operating activities",
    ),
    "Capital Expenditure": (
        "capital expenditure",
        "capital expenditures",
        "capital expenditure purchases",
        "capex",
    ),
    "Total Assets": (
        "total assets",
    ),
    "Total Liabilities": (
        "total liabilities",
    ),
    "Total Equity": (
        "total equity",
        "total shareholders equity",
        "total stockholders equity",
        "shareholders equity",
        "stockholders equity",
    ),
    "Cash and Cash Equivalents": (
        "cash and cash equivalents",
        "cash equivalents",
        "cash and short term investments",
    ),
    "Research and Development Expenses": (
        "research and development expenses",
        "research and development",
        "r&d expenses",
    ),
}



# Explicit SEC XBRL concept mappings.
# Unknown concepts are preserved rather than guessed.

XBRL_METRIC_ALIASES: Final[dict[str, str]] = {
    # Revenue
    "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "Revenues": "Revenue",
    "SalesRevenueNet": "Revenue",

    # Profitability
    "NetIncomeLoss": "Net Income",
    "ProfitLoss": "Net Income",
    "GrossProfit": "Gross Profit",
    "OperatingIncomeLoss": "Operating Income",
    "OperatingExpenses": "Operating Expenses",
    "CostOfRevenue": "Cost of Revenue",

    # Earnings per share
    "EarningsPerShareBasic": "Earnings Per Share",
    "EarningsPerShareDiluted": "Earnings Per Share",

    # Cash flow
    "NetCashProvidedByUsedInOperatingActivities": "Operating Cash Flow",
    "PaymentsToAcquirePropertyPlantAndEquipment": "Capital Expenditure",

    # Balance sheet
    "Assets": "Total Assets",
    "Liabilities": "Total Liabilities",
    "StockholdersEquity": "Total Equity",
    "CashAndCashEquivalentsAtCarryingValue": "Cash and Cash Equivalents",

    # Research and development
    "ResearchAndDevelopmentExpense": "Research and Development Expenses",
}


def get_xbrl_metric_label(concept: str) -> str:
    """
    Normalize an explicitly supported XBRL concept.

    Namespace prefixes such as 'us-gaap:' are removed.
    Unknown concepts are preserved.
    """

    if not isinstance(concept, str):
        raise TypeError("XBRL concept must be a string.")

    concept = concept.strip()

    if not concept:
        return concept

    local_name = concept.rsplit(":", 1)[-1]

    return XBRL_METRIC_ALIASES.get(local_name, concept)

def normalize_metric_label(label: str) -> str | None:
    """
    Normalize a known financial metric label.

    Returns:
        Canonical metric name if an explicit alias matches.
        None if the label is unknown or empty.

    Unknown labels are not guessed or automatically mapped.
    """

    if not isinstance(label, str):
        raise TypeError("Metric label must be a string.")

    normalized = label.strip().lower()

    if not normalized:
        return None

    # Normalize whitespace and common punctuation.
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)

    # Build exact alias lookup.
    for canonical_name, aliases in METRIC_ALIASES.items():
        all_names = (canonical_name.lower(), *aliases)

        if normalized in all_names:
            return canonical_name

    return None


def get_metric_label(label: str) -> str:
    """
    Return the canonical metric name when recognized.
    Preserve unknown labels instead of guessing.
    """

    normalized = normalize_metric_label(label)

    if normalized is not None:
        return normalized

    return label.strip()
