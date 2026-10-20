from pathlib import PurePosixPath

from troubleshooting_agent.connectors.github.client import GitHubConnector

import re

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt",
    ".go", ".rb", ".php", ".cs", ".json", ".yaml", ".yml",
    ".toml", ".xml", ".properties", ".sh", ".sql", ".md",
}

SKIP_DIRECTORIES = {
    "node_modules", "vendor", "dist", "build", ".git",
    "coverage", ".next",
}


def is_searchable_file(path: str) -> bool:
    file_path = PurePosixPath(path)

    if any(part in SKIP_DIRECTORIES for part in file_path.parts):
        return False

    if file_path.name.startswith(".env"):
        return False

    return file_path.suffix.lower() in TEXT_EXTENSIONS





def rank_file(path: str) -> int:
    """Prioritize tests and backend code over generic UI components."""
    file_path = PurePosixPath(path.lower())
    name = file_path.name
    parts = file_path.parts
    suffix = file_path.suffix

    # Tests can provide expected behavior and regression coverage.
    if (
        name.startswith(("test_", "test."))
        or name.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts"))
        or "tests" in parts
        or "__tests__" in parts
    ):
        return 0

        # Networking and error-handling code is especially useful for
    # timeout, connection, and upstream failure investigations.
    if (
        any(term in name for term in ("fetch", "http", "client", "error", "retry", "request"))
        or any(segment in parts for segment in ("network", "middleware"))
    ):
        return 1

    # API and server-side implementation.
    if any(
        segment in parts
        for segment in ("api", "server", "backend")
    ):
        return 2

    # Other application implementation files.
    if suffix in {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
        ".kt", ".go", ".rb", ".php", ".cs",
    }:
        return 2

    # Configuration and deployment definitions.
    if suffix in {
        ".json", ".yaml", ".yml", ".toml", ".xml",
        ".properties", ".sh", ".sql",
    }:
        return 3

    # General documentation is less specific.
    if name in {"readme.md", "changelog.md"}:
        return 5

    return 4



def rank_file_for_query(path: str, query: str) -> int:
    """Prioritize files whose paths match the issue's search terms."""
    normalized_path = path.lower()
    terms = {
        term.casefold()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query)
        if term.casefold() not in {
            "the", "and", "for", "with", "from", "that",
            "this", "are", "was", "were", "when", "how",
        }
    }

    score = sum(2 for term in terms if term in normalized_path)

    # Common implementation locations for specific issue categories.
    if any(term in terms for term in {"timeout", "connection", "network", "retry"}):
        if any(word in normalized_path for word in (
            "fetch", "client", "network", "middleware", "error",
        )):
            score += 5

    if any(term in terms for term in {"authentication", "auth", "login", "token"}):
        if any(word in normalized_path for word in (
            "auth", "login", "customer", "session", "token",
        )):
            score += 5

    return score


def search_repository(
    github: GitHubConnector,
    repository: str,
    query: str,
    branch: str = "main",
    max_files: int = 50,
    max_matches: int = 10,
) -> list[dict[str, str]]:
    """Search a bounded set of text files using GitHub's read-only APIs."""
    query = query.strip()
    if not query:
        raise ValueError("Search query must not be empty.")

    if max_files < 1 or max_files > 100:
        raise ValueError("max_files must be between 1 and 100.")

    if max_matches < 1 or max_matches > 20:
        raise ValueError("max_matches must be between 1 and 20.")

    allowed = getattr(github, "allowed_repositories", set())
    if repository.lower() not in allowed:
        raise ValueError("Repository is outside the configured allowlist.")

    # GitHub API requests are read-only. The repository and branch are explicit.
    tree_response = github._client.get(
        f"{github.base_url}/repos/{repository}/git/trees/{branch}",
        params={"recursive": "1"},
    )
    if tree_response.is_error:
        raise RuntimeError(
            f"Could not retrieve repository tree (HTTP {tree_response.status_code})."
        )

    tree = tree_response.json()
    if tree.get("truncated"):
        raise RuntimeError(
            "GitHub truncated the repository tree; narrow the search scope."
        )

    candidates = [
        item["path"]
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and is_searchable_file(item["path"])
    ]

    
    candidates.sort(
        key=lambda path: (
            -rank_file_for_query(path, query),
            rank_file(path),
            path.lower(),
        )
    )
    candidates = candidates[:max_files]


    results: list[dict[str, str]] = []
    needles = list(dict.fromkeys(
        term.casefold()
        for alternative in query.split("|")
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", alternative)
        if term.casefold() not in {
            "the", "and", "for", "with", "from", "that",
            "this", "are", "was", "were", "when", "how",
        }
    ))
    for path in candidates:
        response = github._client.get(
            f"{github.base_url}/repos/{repository}/contents/{path}",
            params={"ref": branch},
        )
        if response.is_error:
            continue

        data = response.json()

        # Skip binary, oversized, and unsupported content responses.
        if data.get("encoding") != "base64" or not data.get("content"):
            continue
        if data.get("size", 0) > 100_000:
            continue

        import base64

        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue

        
        lines = content.splitlines()
        for line_number, line in enumerate(lines, start=1):
            matched_terms = sum(
                1
                for needle in needles
                if needle in line.casefold()
            )
            minimum_matches = 1 if len(needles) == 1 else 2

            if matched_terms >= minimum_matches:
                results.append(
                    {
                        "repository": repository,
                        "path": path,
                        "line": str(line_number),
                        "url": (
                            f"https://github.com/{repository}/blob/"
                            f"{branch}/{path}#L{line_number}"
                        ),
                        "snippet": line.strip()[:500],
                    }
                )
                if len(results) >= max_matches:
                    return results

    return results

