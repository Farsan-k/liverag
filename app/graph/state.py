
from typing import TypedDict, Any, NotRequired


class ResearchPlan(TypedDict, total=False):
    company: str
    metrics: list[str]
    periods: list[str]
    analysis_type: str
    requires_calculation: bool
    search_requirements: list[str]


class FinancialAnalysis(TypedDict, total=False):
    summary: str
    calculations: list[dict[str, Any]]
    comparisons: list[dict[str, Any]]
    trends: list[dict[str, Any]]
    insights: list[str]
    limitations: list[str]


class VerificationDetails(TypedDict, total=False):
    verified: bool
    errors: list[str]
    calculations: list[dict[str, Any]]


class ResearchState(TypedDict):
    # User input
    question: str
    limit: int

    # Research Agent
    research_plan: NotRequired[ResearchPlan]

    # Retrieval Agent
    retrieved_chunks: NotRequired[list[dict[str, Any]]]
    context: NotRequired[str]
    sources: NotRequired[list[dict[str, Any]]]
    is_sufficient: NotRequired[bool]

    # Analysis Agent
    analysis: NotRequired[FinancialAnalysis]

    # Verification Agent
    verification_result: NotRequired[bool]
    verification_errors: NotRequired[list[str]]
    verification_details: NotRequired[VerificationDetails]

    # Workflow control
    retry_count: NotRequired[int]

    # Response Agent
    answer: NotRequired[str]

    # Error handling
    error: NotRequired[str]
