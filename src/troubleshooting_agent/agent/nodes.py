from troubleshooting_agent.agent.state import InvestigationState


def triage_issue(state: InvestigationState) -> dict:
    """Classify the issue and decide which sources to investigate."""
    question = state["question"]
    text = question.lower()

    if any(word in text for word in ("chef", "recipe", "cookbook", "configuration")):
        issue_type = "configuration"
    elif any(word in text for word in ("confluence", "runbook", "documentation")):
        issue_type = "documentation"
    elif any(word in text for word in ("error", "exception", "500", "failure", "timeout")):
        issue_type = "application"
    else:
        issue_type = "unknown"

    search_plan = [
        "Search Confluence for relevant runbooks and known issues.",
        "Search GitHub for relevant code, error messages, and recent changes.",
        "Search Chef cookbooks for related configuration.",
    ]

    return {
        "issue_type": issue_type,
        "search_plan": search_plan,
    }


def prepare_response(state: InvestigationState) -> dict:
    """Create a preliminary plan; no diagnosis is claimed at this stage."""
    plan = "\n".join(f"- {item}" for item in state["search_plan"])

    response = (
        f"Issue: {state['question']}\n"
        f"Classification: {state['issue_type']}\n\n"
        f"Investigation plan:\n{plan}\n\n"
        "Status: No sources have been searched yet, so no root cause has been established."
    )

    return {"response": response}
