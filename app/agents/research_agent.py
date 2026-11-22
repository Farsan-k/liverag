
from typing import Literal

import ollama
from pydantic import BaseModel, Field, ValidationError

from app.llm import MODEL_NAME
import re

class ResearchPlan(BaseModel):
    """Structured research plan generated from a financial question."""

    company: str | None = Field(
        default=None,
        description="Company explicitly identified in the question.",
    )

    metrics: list[str] = Field(
        default_factory=list,
        description="Financial metrics requested by the user.",
    )

    periods: list[str] = Field(
        default_factory=list,
        description="Reporting periods explicitly requested.",
    )

    analysis_type: Literal[
        "summary",
        "comparison",
        "trend_analysis",
        "ratio_analysis",
        "growth_analysis",
        "cash_flow_analysis",
        "general_analysis",
    ] = "general_analysis"

    requires_calculation: bool = False

    search_requirements: list[str] = Field(
        default_factory=list,
        description="Specific searches needed to answer the question.",
    )



SYSTEM_PROMPT = """
You are the Research Agent of Finova AI, a financial intelligence system.

Your responsibility is to understand financial questions and produce
an accurate structured research plan.

STRICT EXTRACTION RULES:

1. COMPANY
- Identify the company mentioned in the question.
- Do not invent a company.
- If no company is identifiable, return null.

2. FINANCIAL METRICS
- Extract only metrics requested or clearly necessary.
- Examples: Revenue, Net Income, EBITDA, Operating Cash Flow,
  Gross Profit, Net Profit Margin, EPS.
- Do not invent additional metrics.

3. REPORTING PERIODS
- Extract only reporting periods explicitly mentioned.
- Examples: FY2024, FY2025, Q1 2025, March 2025.
- Never invent reporting periods.
- Never use "All Time", "Latest", or arbitrary dates
  as reporting periods unless explicitly requested.
- If no reporting period is specified, return an empty list.
- For a period range, identify the relevant periods without
  inventing unsupported dates.

4. ANALYSIS TYPE

Choose the most appropriate category:

- summary: General financial overview or summary.
- comparison: Comparing two or more financial values.
- trend_analysis: Examining changes over time.
- ratio_analysis: Profit margins and financial ratios.
- growth_analysis: Revenue, profit or other growth calculations.
- cash_flow_analysis: Cash flow-specific analysis.
- general_analysis: Other financial questions.

Important examples:
- Net profit margin calculation -> ratio_analysis.
- Revenue growth comparison -> growth_analysis.
- Operating cash flow trend -> cash_flow_analysis.
- General company financial summary -> summary.

5. CALCULATION REQUIREMENT

Set requires_calculation to true when the question requires:
- Growth percentage calculations.
- Profit margin calculations.
- Financial ratio calculations.
- Numerical comparisons or differences.
- Trend calculations.

Set it to false when the user only requests a descriptive summary
or extraction of an existing financial figure.

6. SEARCH REQUIREMENTS
- Create searches using only the identified company, metrics
  and reporting periods.
- Never invent a reporting period to construct a search.
- If no reporting period is specified, create a search that
  does not assume a particular period.
- Return an empty list if no useful search can be constructed.

7. GENERAL SAFETY
- Never invent financial figures.
- Never invent companies, reporting periods or metrics.
- Do not answer the user's financial question.
- Do not use outside knowledge to fill missing information.
- Return only data matching the structured schema.
"""





def normalize_research_plan(
    question: str,
    plan: ResearchPlan,
) -> ResearchPlan:
    """
    Normalize the LLM-generated research plan using
    deterministic rules based on the original question.
    """

    question_lower = question.lower()

    # --------------------------------------------------
    # 1. Extract financial metrics from the question
    # --------------------------------------------------

    metric_patterns = {
        "Operating Cash Flow": [
            r"\boperating cash flow\b",
            r"\boperating cash flows\b",
            r"\bcash flow from operations\b",
        ],
        "Net Profit Margin": [
            r"\bnet profit margin\b",
            r"\bnet margin\b",
        ],
        "Gross Profit Margin": [
            r"\bgross profit margin\b",
            r"\bgross margin\b",
        ],
        "Revenue": [
            r"\brevenue\b",
            r"\brevenues\b",
            r"\bnet sales\b",
        ],
        "Net Income": [
            r"\bnet income\b",
            r"\bnet profit\b",
        ],
        "Operating Income": [
            r"\boperating income\b",
            r"\boperating profit\b",
        ],
        "EBITDA": [
            r"\bebitda\b",
        ],
        "EPS": [
            r"\beps\b",
            r"\bearnings per share\b",
        ],
        "Gross Profit": [
            r"\bgross profit\b",
        ],
        "Free Cash Flow": [
            r"\bfree cash flow\b",
        ],
    }

    extracted_metrics = []

    for metric, patterns in metric_patterns.items():
        if any(
            re.search(pattern, question_lower)
            for pattern in patterns
        ):
            extracted_metrics.append(metric)

    if extracted_metrics:
        plan.metrics = extracted_metrics

    # --------------------------------------------------
    # 2. Extract fiscal years
    # --------------------------------------------------

    fiscal_years = re.findall(
        r"\bFY[\s-]?(\d{4})\b",
        question,
        flags=re.IGNORECASE,
    )

    fiscal_years = list(dict.fromkeys(fiscal_years))

    # --------------------------------------------------
    # 3. Expand explicitly requested fiscal-year ranges
    # --------------------------------------------------

    range_match = re.search(
        r"\b(?:between|from)\s+FY[\s-]?(\d{4})"
        r"\s+(?:and|to|through)\s+FY[\s-]?(\d{4})\b",
        question,
        flags=re.IGNORECASE,
    )

    if range_match:
        start_year = int(range_match.group(1))
        end_year = int(range_match.group(2))

        if start_year <= end_year and end_year - start_year <= 30:
            fiscal_years = [
                str(year)
                for year in range(start_year, end_year + 1)
            ]

    if fiscal_years:
        plan.periods = [
            f"FY{year}"
            for year in fiscal_years
        ]
    else:
        # Do not retain periods invented by the LLM.
        plan.periods = []

    # --------------------------------------------------
    # 4. Correct analysis classification
    # --------------------------------------------------

    if re.search(
        r"\b(cash flow|cash flows)\b",
        question_lower,
    ):
        plan.analysis_type = "cash_flow_analysis"

    elif re.search(
        r"\b(margin|margins|financial ratio|ratios)\b",
        question_lower,
    ):
        plan.analysis_type = "ratio_analysis"

    elif re.search(
        r"\b(growth|grow|grew|growth rate)\b",
        question_lower,
    ):
        plan.analysis_type = "growth_analysis"

    elif re.search(
        r"\b(compare|comparison|versus|vs\.?)\b",
        question_lower,
    ):
        plan.analysis_type = "comparison"

    elif re.search(
        r"\b(trend|trends|over time)\b",
        question_lower,
    ):
        plan.analysis_type = "trend_analysis"

    elif re.search(
        r"\b(summary|summarize|overview)\b",
        question_lower,
    ):
        plan.analysis_type = "summary"

    # --------------------------------------------------
    # 5. Determine whether calculation is required
    # --------------------------------------------------

    calculation_patterns = [
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bpercentage\b",
        r"\bgrowth\b",
        r"\bgrowth rate\b",
        r"\bmargin\b",
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bdifference\b",
        r"\bchange\b",
        r"\btrend\b",
        r"\btrends\b",
        r"\bhow much\b",
    ]

    plan.requires_calculation = any(
        re.search(pattern, question_lower)
        for pattern in calculation_patterns
    )

    # --------------------------------------------------
    # 6. Generate search requirements deterministically
    # --------------------------------------------------

    search_requirements = []

    if plan.metrics:
        for metric in plan.metrics:
            if plan.periods:
                for period in plan.periods:
                    parts = []

                    if plan.company:
                        parts.append(plan.company)

                    parts.extend([period, metric])

                    search_requirements.append(
                        " ".join(parts)
                    )
            else:
                parts = []

                if plan.company:
                    parts.append(plan.company)

                parts.append(metric)

                search_requirements.append(
                    " ".join(parts)
                )

    elif plan.company:
        search_requirements.append(plan.company)

    plan.search_requirements = search_requirements

    return plan





def create_research_plan(question: str) -> ResearchPlan:
    """
    Generate a structured research plan using Ollama
    and normalize it using deterministic Python rules.
    """

    if not question or not question.strip():
        raise ValueError("Research question cannot be empty.")

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": question.strip(),
                },
            ],
            format=ResearchPlan.model_json_schema(),
            options={
                "temperature": 0,
            },
        )

        content = response["message"]["content"].strip()

        if not content:
            raise ValueError(
                "Ollama returned an empty research plan."
            )

        # Validate the LLM-generated plan
        plan = ResearchPlan.model_validate_json(content)

        # Apply deterministic normalization
        plan = normalize_research_plan(
            question=question.strip(),
            plan=plan,
        )

        return plan

    except ValidationError as exc:
        raise ValueError(
            f"Invalid research plan returned by Ollama: {exc}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Research planning failed: {exc}"
        ) from exc

