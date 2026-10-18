from typing import Literal, TypedDict


class InvestigationState(TypedDict, total=False):
    question: str
    issue_type: Literal["application", "configuration", "documentation", "unknown"]
    search_plan: list[str]
    response: str
