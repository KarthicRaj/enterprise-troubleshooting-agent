from pathlib import PurePosixPath

from troubleshooting_agent.connectors.github.client import GitHubConnector


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
    ][:max_files]

    results: list[dict[str, str]] = []
    needle = query.casefold()

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
            if needle in line.casefold():
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
