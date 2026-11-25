
from langgraph.graph import StateGraph, START, END

from app.graph.state import ResearchState

from app.graph.nodes import (
    research_node,
    retrieve_node,
    validate_evidence_node,
    analysis_node,
    verification_node,
    generate_answer_node,
)


def route_after_research(state: ResearchState) -> str:
    """Check whether research planning succeeded."""

    if state.get("error"):
        return "end"

    return "retrieve"


def route_after_retrieval(state: ResearchState) -> str:
    """Choose the descriptive or calculation workflow."""

    research_plan = state.get("research_plan", {})

    if research_plan.get("requires_calculation", False):
        return "analysis"

    return "validate_evidence"


def route_after_validation(state: ResearchState) -> str:
    """Continue only when descriptive evidence is sufficient."""

    if state.get("is_sufficient", False):
        return "generate_answer"

    return "end"


def route_after_analysis(state: ResearchState) -> str:
    """Send analysis results to independent verification."""

    return "verification"


def route_after_verification(state: ResearchState) -> str:
    """Send verified or blocked results to the response node."""

    return "generate_answer"


def build_research_graph():
    """Build and compile the Finova AI multi-agent workflow."""

    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("research", research_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("validate_evidence", validate_evidence_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("verification", verification_node)
    graph.add_node("generate_answer", generate_answer_node)

    # Start
    graph.add_edge(START, "research")

    # Research planning
    graph.add_conditional_edges(
        "research",
        route_after_research,
        {
            "retrieve": "retrieve",
            "end": END,
        },
    )

    # Select descriptive or calculation path
    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieval,
        {
            "validate_evidence": "validate_evidence",
            "analysis": "analysis",
        },
    )

    # Descriptive path
    graph.add_conditional_edges(
        "validate_evidence",
        route_after_validation,
        {
            "generate_answer": "generate_answer",
            "end": END,
        },
    )

    # Calculation path
    graph.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "verification": "verification",
        },
    )

    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "generate_answer": "generate_answer",
        },
    )

    # Final response
    graph.add_edge("generate_answer", END)

    return graph.compile()


research_graph = build_research_graph()
