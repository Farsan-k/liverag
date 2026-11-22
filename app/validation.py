import re
from decimal import Decimal, InvalidOperation

FALLBACK_ANSWER = (
    "I do not have enough information to answer this question."
)

MONTH_NAMES = (
    "january", "february", "march", "april",
    "may", "june", "july", "august",
    "september", "october", "november", "december",
)

def has_matching_time_period(question: str, context: str) -> bool:
    """Check whether requested years and months exist in the evidence."""

    question_lower = question.lower()
    context_lower = context.lower()

    year_pattern = r"(?<!\d)(?:FY\s*)?((?:19|20|21)\d{2})\b"

    question_years = set(re.findall(year_pattern, question_lower))
    context_years = set(re.findall(year_pattern, context_lower))

    if question_years and not question_years.issubset(context_years):
        return False

    requested_months = {
        month for month in MONTH_NAMES
        if re.search(rf"\b{month}\b", question_lower)
    }

    available_months = {
        month for month in MONTH_NAMES
        if re.search(rf"\b{month}\b", context_lower)
    }

    if requested_months and not requested_months.issubset(available_months):
        return False

    return True

def has_matching_metric(question: str, context: str) -> bool:
    """
    Check whether requested financial metrics have numeric
    supporting evidence in the retrieved context.
    """

    metric_keywords = {
        "revenue": (
            "revenue",
            "net sales",
            "total sales",
            "sales",
            "turnover",
        ),
        "net profit": ("net profit", "net income"),
        "gross profit": ("gross profit",),
        "operating profit": ("operating profit",),
        "profit": ("profit", "earnings"),
        "expenses": ("expenses", "expenditure", "costs"),
        "cash flow": ("cash flow",),
        "assets": ("assets",),
        "liabilities": ("liabilities",),
        "debt": ("debt",),
    }

    question_lower = question.lower()
    context_lower = context.lower()

    requested_metrics = [
        (metric, keywords)
        for metric, keywords in metric_keywords.items()
        if re.search(rf"\b{re.escape(metric)}\b", question_lower)
    ]

    if not requested_metrics:
        return True

    # Avoid treating "net profit" as two separate requested metrics.
    specific_profit_metrics = {
        "net profit",
        "gross profit",
        "operating profit",
    }

    if any(metric in specific_profit_metrics for metric, _ in requested_metrics):
        requested_metrics = [
            (metric, keywords)
            for metric, keywords in requested_metrics
            if metric != "profit"
        ]

    clauses = re.split(
        r"(?<=[.!?])\s+|[,;]|\s+(?:and|while|whereas|but)\s+",
        context_lower,
        flags=re.IGNORECASE,
    )

    for metric, keywords in requested_metrics:
        supported = False

        for clause in clauses:
            metric_found = any(
                re.search(rf"\b{re.escape(keyword)}\b", clause)
                for keyword in keywords
            )

            if not metric_found:
                continue

            numbers = extract_normalized_numbers(
                clause,
                exclude_years=True,
            )

            if numbers:
                supported = True
                break

        if not supported:
            return False

    return True


def has_matching_metric_period(
    question: str,
    context: str,
) -> bool:
    """Verify requested metrics have numeric evidence for the requested period."""

    question_lower = question.lower()

    requested_months = {
        month
        for month in MONTH_NAMES
        if re.search(rf"\b{month}\b", question_lower)
    }

    requested_years = set(
        re.findall(
            r"(?<!\d)(?:FY\s*)?((?:19|20|21)\d{2})\b",
            question_lower,
        )
    )

    if not requested_months and not requested_years:
        return True

    metric_keywords = {
        "revenue": (
            "revenue",
            "net sales",
            "total sales",
            "sales",
            "turnover",
        ),
        "net profit": ("net profit", "net income"),
        "gross profit": ("gross profit",),
        "operating profit": ("operating profit",),
        "profit": ("profit", "earnings"),
        "expenses": ("expenses", "expenditure", "costs"),
        "cash flow": ("cash flow",),
        "assets": ("assets",),
        "liabilities": ("liabilities",),
        "debt": ("debt",),
    }

    # Detect metrics using both canonical names and their aliases.
    requested_metrics = [
        (metric, keywords)
        for metric, keywords in metric_keywords.items()
        if any(
            re.search(rf"\b{re.escape(keyword)}\b", question_lower)
            for keyword in keywords
        )
    ]

    if not requested_metrics:
        return True

    specific_profit_metrics = {
        "net profit",
        "gross profit",
        "operating profit",
    }

    if any(
        metric in specific_profit_metrics
        for metric, _ in requested_metrics
    ):
        requested_metrics = [
            item
            for item in requested_metrics
            if item[0] != "profit"
        ]

    clauses = re.split(
        r"(?<=[.!?])\s+|[,;]|\s+(?:and|while|whereas|but)\s+",
        context.lower(),
        flags=re.IGNORECASE,
    )

    for metric, keywords in requested_metrics:
        supported = False

        for index, clause in enumerate(clauses):
            if not any(
                re.search(rf"\b{re.escape(keyword)}\b", clause)
                for keyword in keywords
            ):
                continue

            effective_text = clause

            # A reporting-period heading applies only to the next clause.
            if index > 0 and re.search(
                r"(?:reporting\s+period|period|for\s+the\s+period)\s*:",
                clauses[index - 1],
            ):
                heading_match = re.search(
                    r"(?:reporting\s+period|period|for\s+the\s+period)"
                    r"\s*:\s*(.*)",
                    clauses[index - 1],
                )

                if heading_match:
                    effective_text = (
                        f"{heading_match.group(1)} {clause}"
                    )

            has_amount = bool(
                extract_normalized_numbers(
                    clause,
                    exclude_years=True,
                )
            )

            has_month = all(
                re.search(rf"\b{month}\b", effective_text)
                for month in requested_months
            )

            # Supports both FY2025 and 2025.
            has_year = all(
                re.search(
                    rf"(?<!\d)(?:fy\s*)?{year}\b",
                    effective_text,
                )
                for year in requested_years
            )

            if has_amount and has_month and has_year:
                supported = True
                break

        if not supported:
            return False

    return True


FINANCIAL_SCALES = {
    "thousand": Decimal("1000"),
    "thousands": Decimal("1000"),
    "lakh": Decimal("100000"),
    "lakhs": Decimal("100000"),
    "lac": Decimal("100000"),
    "lacs": Decimal("100000"),
    "crore": Decimal("10000000"),
    "crores": Decimal("10000000"),
    "million": Decimal("1000000"),
    "millions": Decimal("1000000"),
    "billion": Decimal("1000000000"),
    "billions": Decimal("1000000000"),
}

def normalize_financial_number(
    number: str,
    scale: str | None = None,
    is_percentage: bool = False,
) -> str:
    """Normalize financial amounts to a comparable numeric value."""

    value = Decimal(number.replace(",", ""))

    if scale:
        value *= FINANCIAL_SCALES[scale.lower()]

    normalized = format(value.normalize(), "f")

    return f"{normalized}%" if is_percentage else normalized

def extract_normalized_numbers(
    text: str,
    exclude_years: bool = False,
) -> set[str]:
    """Extract normalized numbers, including financial unit conversions."""

    pattern = re.compile(
        r"(?<![\w.])"
        r"(?P<number>[+-]?\d[\d,]*(?:\.\d+)?)"
        r"(?:\s*(?P<scale>thousands?|lakhs?|lacs?|crores?|millions?|billions?))?"
        r"(?:\s*(?P<percentage>%|percent(?:age)?))?"
        r"(?!\w)",
        re.IGNORECASE,
    )

    numbers = set()

    for match in pattern.finditer(text):
        number = match.group("number")
        scale = match.group("scale")
        percentage = match.group("percentage")

        if exclude_years and not scale and re.fullmatch(
            r"(?:19|20)\d{2}", number
        ):
            continue

        try:
            numbers.add(
                normalize_financial_number(
                    number,
                    scale,
                    bool(percentage),
                )
            )
        except (InvalidOperation, ValueError):
            continue

    return numbers

def answer_numbers_match_context(answer: str, context: str) -> bool:
    """Reject numeric values that are not supported by the evidence."""

    answer_numbers = extract_normalized_numbers(answer)
    context_numbers = extract_normalized_numbers(context)

    return answer_numbers.issubset(context_numbers)

def is_descriptive_financial_question(question: str) -> bool:
    """Identify questions asking for explanations rather than amounts."""

    question_lower = question.lower()

    descriptive_patterns = (
        r"\bwhat (?:drove|caused|explains?)\b",
        r"\bwhy did .*\b(?:grow|increase|decline|decrease|change)\b",
        r"\b(?:drivers|factors|reasons) behind\b",
        r"\bwhat (?:were|are) the (?:main )?"
        r"(?:drivers|factors|reasons)\b",
        r"\bhow did .*\b(?:grow|increase|decline|decrease|perform|change)\b",
    )

    return any(
        re.search(pattern, question_lower)
        for pattern in descriptive_patterns
    )

def answer_metric_numbers_match_context(
    question: str,
    answer: str,
    context: str,
) -> bool:
    """Verify numeric answers for every requested financial metric."""

    metric_keywords = {
        "revenue": ("sales", "turnover"),
        "net profit": ("net income",),
        "gross profit": (),
        "operating profit": (),
        "cash flow": (),
        "expenses": ("expenditure", "costs"),
        "assets": (),
        "liabilities": (),
        "debt": (),
    }

    question_lower = question.lower()

    requested_metrics = [
        metric
        for metric, aliases in metric_keywords.items()
        if any(
            re.search(rf"\b{re.escape(alias)}\b", question_lower)
            for alias in (metric, *aliases)
        )
    ]

    if not requested_metrics:
        return True

    def metric_numbers(
        text: str,
        aliases: tuple[str, ...],
    ) -> set[str]:
        numbers = set()

        for sentence in re.split(r"(?<=[.!?])\s+", text):
            clauses = re.split(
                r"\s+(?:and|while|whereas|but)\s+",
                sentence,
                flags=re.IGNORECASE,
            )

            for clause in clauses:
                clause_lower = clause.lower()

                if any(
                    re.search(
                        rf"\b{re.escape(alias)}\b",
                        clause_lower,
                    )
                    for alias in aliases
                ):
                    numbers.update(
                        extract_normalized_numbers(
                            clause,
                            exclude_years=True,
                        )
                    )

        return numbers

    for metric in requested_metrics:
        aliases = (metric, *metric_keywords[metric])

        answer_numbers = metric_numbers(answer, aliases)

        # Allow a number-only answer when exactly one metric was requested.
        if not answer_numbers and len(requested_metrics) == 1:
            answer_numbers = extract_normalized_numbers(
                answer,
                exclude_years=True,
            )

        evidence_numbers = metric_numbers(context, aliases)

        # Descriptive questions do not require a metric amount in the answer.
        if (
            not answer_numbers
            and is_descriptive_financial_question(question)
        ):
            continue

        # Reject answers that omit the requested metric's amount.
        if not answer_numbers:
            return False

        # Reject when the evidence has no supporting amount.
        if not evidence_numbers:
            return False

        # Reject numbers that do not match the evidence.
        if not answer_numbers.issubset(evidence_numbers):
            return False

    return True

def answer_currency_matches_context(
    answer: str,
    context: str,
) -> bool:
    """Ensure currency and normalized amounts match the evidence."""

    number_pattern = r"[+-]?\d[\d,]*(?:\.\d+)?"

    currency_pattern = re.compile(
        rf"(?:(?P<prefix>₹|(?<!\w)INR\b|(?<!\w)USD\b|"
        rf"(?<!\w)US\s+dollars?\b|(?<!\w)Rs\.?|(?<!\w)\$)\s*)?"
        rf"(?P<number>{number_pattern})"
        rf"(?:\s*(?P<scale>thousands?|lakhs?|lacs?|crores?|millions?|billions?))?"
        rf"(?:\s*(?P<suffix>rupees?\b|INR\b|USD\b|"
        rf"US\s+dollars?\b|dollars?\b))?",
        re.IGNORECASE,
    )

    def extract_currency_claims(
        text: str,
    ) -> set[tuple[str, str]]:
        claims = set()

        for match in currency_pattern.finditer(text):
            prefix = match.group("prefix")
            suffix = match.group("suffix")

            if not prefix and not suffix:
                continue

            marker = (prefix or suffix).lower()

            if marker in {"₹", "inr", "rs", "rs.", "rupee", "rupees"}:
                currency = "INR"
            elif marker in {
                "$", "usd", "us dollar", "us dollars",
                "dollar", "dollars",
            }:
                currency = "USD"
            else:
                continue

            try:
                amount = normalize_financial_number(
                    match.group("number"),
                    match.group("scale"),
                )
            except (InvalidOperation, ValueError):
                continue

            claims.add((amount, currency))

        return claims

    answer_claims = extract_currency_claims(answer)
    context_claims = extract_currency_claims(context)

    return answer_claims.issubset(context_claims)

def requires_metric_amount(question: str) -> bool:
    """
    Determine whether the question explicitly requests
    a numerical amount for a financial metric.
    """
    question_lower = question.lower()

    amount_patterns = (
        r"\bhow much\b",
        r"\bwhat (?:was|is|were|are) the "
        r"(?:total )?(?:amount|value)\b",
        r"\b(?:revenue|sales|profit|income|cash flow|"
        r"expenses|assets|liabilities|debt)\s+amount\b",
        r"\b(?:amount|value|figure)\s+of\b",
    )

    return any(
        re.search(pattern, question_lower)
        for pattern in amount_patterns
    )

def has_monetary_amount(text: str) -> bool:
    """Check whether text contains an explicitly identified monetary amount."""

    monetary_pattern = re.compile(
        r"(?:(?:₹|\$|INR\b|USD\b|Rs\.?)\s*"
        r"\d[\d,]*(?:\.\d+)?"
        r"(?:\s*(?:thousands?|lakhs?|lacs?|crores?|millions?|billions?))?"
        r"|"
        r"\d[\d,]*(?:\.\d+)?\s*"
        r"(?:thousands?|lakhs?|lacs?|crores?|millions?|billions?)"
        r"\s*(?:INR|USD|rupees?|dollars?)\b)",
        re.IGNORECASE,
    )

    return bool(monetary_pattern.search(text))

def has_matching_metric_category_amount(
    question: str,
    context: str,
) -> bool:
    """Check that requested categories have matching monetary evidence."""

    category_keywords = {
        "product": ("iphone", "mac", "ipad"),
        "service": ("services",),
        "geography": (
            "americas", "europe", "greater china",
            "china", "japan", "asia pacific",
        ),
        "business segment": ("products", "services"),
    }

    metric_keywords = {
        "revenue": ("revenue", "net sales", "total sales", "sales", "turnover"),
        "profit": ("profit",),
        "net profit": ("net profit", "net income"),
        "gross profit": ("gross profit",),
        "operating profit": ("operating profit",),
        "cash flow": ("cash flow",),
        "expenses": ("expenses", "expenditure", "costs"),
        "assets": ("assets",),
        "liabilities": ("liabilities",),
        "debt": ("debt",),
    }

    question_lower = question.lower()
    context_lower = context.lower()

    def find_matches(text, keywords):
        return {
            keyword
            for keyword in keywords
            if re.search(rf"\b{re.escape(keyword)}\b", text)
        }

    all_categories = {
        keyword
        for keywords in category_keywords.values()
        for keyword in keywords
    }

    requested_categories = find_matches(
        question_lower,
        all_categories,
    )

    if not requested_categories:
        return True

    requested_metrics = {
        metric
        for metric, aliases in metric_keywords.items()
        if find_matches(question_lower, (metric, *aliases))
    }

    if not requested_metrics:
        return False

    specific_profit_metrics = {
        "net profit",
        "gross profit",
        "operating profit",
    }

    if requested_metrics & specific_profit_metrics:
        requested_metrics.discard("profit")

    # Split the question into related parts.
    question_parts = re.split(
        r"\s+(?:and|while|whereas|but)\s+|[,;]",
        question_lower,
    )

    # Associate categories and metrics within each part.
    associations = []
    previous_categories = set()
    previous_metrics = set()

    for part in question_parts:
        categories = find_matches(part, all_categories)

        metrics = {
            metric
            for metric, aliases in metric_keywords.items()
            if find_matches(part, (metric, *aliases))
            and metric in requested_metrics
        }

        if categories and metrics:
            associations.append((categories, metrics))
            previous_categories = categories
            previous_metrics = metrics

        elif categories:
            if previous_metrics:
                associations.append((categories, previous_metrics))
            previous_categories = categories

        elif metrics:
            if previous_categories:
                associations.append((previous_categories, metrics))
            previous_metrics = metrics

    if not associations:
        return False

    # Ensure every requested category and metric is represented.
    associated_categories = set()
    associated_metrics = set()

    for categories, metrics in associations:
        associated_categories.update(categories)
        associated_metrics.update(metrics)

    if not requested_categories.issubset(associated_categories):
        return False

    if not requested_metrics.issubset(associated_metrics):
        return False

    # Split retrieved evidence into individual clauses.
    context_clauses = re.split(
        r"(?<=[.!?])\s+|[,;]|\s+(?:and|while|whereas|but)\s+",
        context_lower,
        flags=re.IGNORECASE,
    )

    # Validate each category-metric association independently.
    for categories, metrics in associations:
        for category in categories:
            for metric in metrics:
                aliases = metric_keywords[metric]

                supported = any(
                    re.search(
                        rf"\b{re.escape(category)}\b",
                        clause,
                    )
                    and any(
                        re.search(
                            rf"\b{re.escape(alias)}\b",
                            clause,
                        )
                        for alias in (metric, *aliases)
                    )
                    and has_monetary_amount(clause)
                    for clause in context_clauses
                )

                if not supported:
                    return False

    return True
