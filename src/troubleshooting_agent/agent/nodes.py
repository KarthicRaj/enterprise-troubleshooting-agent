from troubleshooting_agent.agent.state import InvestigationState

import os

from dotenv import load_dotenv
from pathlib import PurePosixPath

from troubleshooting_agent.agent.state import InvestigationState
from troubleshooting_agent.connectors.github.client import GitHubConnector
from troubleshooting_agent.connectors.github.search import search_repository
from troubleshooting_agent.agent.prompts import load_agent_instructions

def triage_issue(state: InvestigationState) -> dict:
    """Classify the issue and decide which sources to investigate."""
    question = state["question"]
    text = question.lower()
    agent_instructions = load_agent_instructions()
    if any(word in text for word in ("chef", "recipe", "cookbook", "configuration")):
        issue_type = "configuration"
    elif any(word in text for word in ("confluence", "runbook", "documentation")):
        issue_type = "documentation"
    elif any(word in text for word in ("error",
        "exception",
        "500",
        "failure",
        "timeout",
        "login",
        "authentication",
        "auth",
        "validation",
        "email")):
        issue_type = "application"
    else:
        issue_type = "unknown"

    search_plan = [
       "Search the approved GitHub repository for relevant source code.",
        "Review matching code snippets and source links.",
        "Determine whether the available evidence is sufficient to identify a likely cause.",
    ]

    return {
        "issue_type": issue_type,
        "search_plan": search_plan,
        "agent_instructions": agent_instructions
    }      




def relevance_score(item: dict, question: str = "") -> int:
    path = item["path"].lower()
    snippet = item["snippet"].lower()
    score = 0

    if "auth" in path or "login" in path:
        score += 5

    for keyword in ("email", "validation", "validate", "login", "auth"):
        if keyword in snippet:
            score += 3
        if keyword in path:
            score += 2

    if PurePosixPath(path).suffix in {
        ".ts", ".tsx", ".js", ".jsx", ".py", ".java"
    }:
        score += 2

    return score


def prepare_response(state: InvestigationState) -> dict:
    plan = "\n".join(
        f"- {item}" for item in state.get("search_plan", [])
    )
    instructions = state.get("agent_instructions", "")

    if not instructions:
        raise ValueError(
            "Agent instructions are missing from the investigation state."
        )
    results = state.get("github_results", [])
    results = sorted(results,key=lambda item: relevance_score(item),reverse=True,)
   
    search_error = state.get("github_search_error")

    if results:
        evidence = []
        for item in results:
            evidence.append(
                f"- **{item['path']}:{item['line']}**\n"
                f"  - Snippet: `{item['snippet']}`\n"
                f"  - Source: {item['url']}"
            )
        evidence_text = "\n".join(evidence)
    else:
        evidence_text = (
            "No matching source-code lines were found in the files searched."
        )

    if search_error:
        evidence_text += f"\n\nGitHub search error: {search_error}"

    response = (
        f"Issue: {state.get('question', '')}\n"
        f"Classification: {state.get('issue_type', 'unknown')}\n\n"
        f"GitHub findings:\n{evidence_text}\n\n"
        f"Investigation plan:\n{plan}\n\n"
        "Status: These are search findings, not a confirmed root cause. "
        "Additional investigation may be required."
    )

    return {"response": response}





def search_github(state: InvestigationState) -> dict:
    """Search approved repository files using targeted issue keywords."""
    import os
    import re
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(".env"))

    repository = os.getenv("GITHUB_ALLOWED_REPOSITORIES", "").split(",")[0].strip()
    repository = repository.removeprefix("https://github.com/").rstrip("/")

    if not repository:
        return {"github_results": []}

    question = state.get("question", "").strip()
    if not question:
        return {"github_results": []}

    # Extract useful terms instead of searching for the entire sentence.
    stop_words = {
        "the", "a", "an", "is", "has", "have", "with", "for", "on",
        "in", "to", "and", "or", "of", "my", "our", "issue", "problem",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question.lower())
    keywords = list(dict.fromkeys(
        word for word in words if word not in stop_words
    ))[:5]

    all_results = []
    seen = set()

    try:
        with GitHubConnector() as github:
            for keyword in keywords:
                results = search_repository(
                    github=github,
                    repository=repository,
                    query=keyword,
                    branch="main",
                    max_files=50,
                    max_matches=5,
                )

                for result in results:
                    key = (result["path"], result["line"])
                    if key not in seen:
                        seen.add(key)
                        all_results.append(result)

                if len(all_results) >= 10:
                    break

        return {"github_results": all_results[:10]}

    except Exception as exc:
        return {
            "github_results": all_results[:10],
            "github_search_error": f"{type(exc).__name__}: {exc}",
        }

