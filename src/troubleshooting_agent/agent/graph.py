from langgraph.graph import END, START, StateGraph

from troubleshooting_agent.agent.nodes import prepare_response, triage_issue
from troubleshooting_agent.agent.state import InvestigationState


def build_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("triage", triage_issue)
    graph.add_node("prepare_response", prepare_response)

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "prepare_response")
    graph.add_edge("prepare_response", END)

    return graph.compile()


agent = build_graph()
