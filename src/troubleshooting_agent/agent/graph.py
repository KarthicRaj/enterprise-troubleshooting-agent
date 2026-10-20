
from langgraph.graph import END, START, StateGraph

from troubleshooting_agent.agent.state import InvestigationState

from troubleshooting_agent.agent.nodes import (
    diagnose_issue,
    handle_out_of_scope,
    prepare_response,
    search_github,
    search_splunk,
    triage_issue,
    handle_uncertain_scope
)


def route_after_triage(state: InvestigationState) -> str:
    status = state.get("scope_status", "uncertain")

    if status == "in_scope":
        return "investigate"
    if status == "out_of_scope":
        return "out_of_scope"

    return "uncertain"



def build_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("triage", triage_issue)
    graph.add_node("handle_out_of_scope", handle_out_of_scope)
    graph.add_node("handle_uncertain_scope", handle_uncertain_scope)
    graph.add_node("search_github", search_github)
    graph.add_node("search_splunk", search_splunk)
    graph.add_node("diagnose_issue", diagnose_issue)
    graph.add_node("prepare_response", prepare_response)

    graph.add_edge(START, "triage")

    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "investigate": "search_github",
            "out_of_scope": "handle_out_of_scope",
            "uncertain": "handle_uncertain_scope",
        }
    )

    graph.add_edge("handle_out_of_scope", END)
    graph.add_edge("search_github", "search_splunk")
    graph.add_edge("search_splunk", "diagnose_issue")
    graph.add_edge("diagnose_issue", "prepare_response")
    graph.add_edge("prepare_response", END)

    return graph.compile()

agent = build_graph()

