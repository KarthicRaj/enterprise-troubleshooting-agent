
from langgraph.graph import END, START, StateGraph

from troubleshooting_agent.agent.state import InvestigationState

from troubleshooting_agent.agent.nodes import (
    diagnose_issue,
    prepare_response,
    search_splunk,
    search_github,
    triage_issue,
)



def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("diagnose_issue", diagnose_issue)
    graph.add_node("triage", triage_issue)
    graph.add_node("search_github", search_github)
    graph.add_node("search_splunk", search_splunk)
    graph.add_node("prepare_response", prepare_response)

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "search_github")
    graph.add_edge("search_github", "search_splunk")
    graph.add_edge("search_splunk", "diagnose_issue")
    graph.add_edge("diagnose_issue", "prepare_response")
    graph.add_edge("prepare_response", END)

    return graph.compile()


agent = build_graph()
