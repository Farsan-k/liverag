
from langgraph.graph import StateGraph, START, END

from app.graph.state import ResearchState
from app.graph.nodes import (
    retrieve_node,
    validate_evidence_node,
    generate_answer_node,
)


def route_after_validation(state: ResearchState) -> str:
    """
    Decide whether to generate an answer or stop.
    """

    if state["is_sufficient"]:
        return "generate_answer"

    return "end"


def build_research_graph():
    """
    Build and compile the Finova AI research workflow.
    """

    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("validate_evidence", validate_evidence_node)
    graph.add_node("generate_answer", generate_answer_node)

    # Define workflow
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "validate_evidence")

    # Conditional routing
    graph.add_conditional_edges(
        "validate_evidence",
        route_after_validation,
        {
            "generate_answer": "generate_answer",
            "end": END,
        },
    )

    graph.add_edge("generate_answer", END)

    return graph.compile()


research_graph = build_research_graph()
