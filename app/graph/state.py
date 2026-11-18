
from typing import TypedDict, Any


class ResearchState(TypedDict):
    # User input
    question: str
    limit: int

    # Retrieved information
    retrieved_chunks: list[dict[str, Any]]
    context: str
    sources: list[dict[str, Any]]

    # Evidence validation
    is_sufficient: bool

    # Generated response
    answer: str

    # Error handling
    error: str
