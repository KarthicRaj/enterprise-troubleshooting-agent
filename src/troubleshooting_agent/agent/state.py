
from typing import Literal, TypedDict


class GitHubSearchResult(TypedDict):
    repository: str
    path: str
    line: str
    url: str
    snippet: str


class InvestigationState(TypedDict, total=False):
    question: str
    issue_type: Literal["application", "configuration", "documentation", "unknown"]
    search_plan: list[str]
    github_results: list[GitHubSearchResult]
    response: str
    agent_instructions: str
    diagnosis: str
