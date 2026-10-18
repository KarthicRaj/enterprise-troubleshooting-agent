
import os
import re
from typing import Any

import httpx


_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubConnectorError(RuntimeError):
    """Raised when a GitHub API request cannot be completed safely."""


class GitHubConnector:
    """Read-only GitHub code search restricted to an explicit repository allowlist."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        allowed_repositories: list[str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.base_url = (
            base_url or os.getenv("GITHUB_API_URL", "https://api.github.com")
        ).rstrip("/")

        configured_repositories = allowed_repositories
        if configured_repositories is None:
            configured_repositories = [
                item.strip()
                for item in os.getenv("GITHUB_ALLOWED_REPOSITORIES", "").split(",")
                if item.strip()
            ]

        self.allowed_repositories = {
            repository.lower() for repository in configured_repositories
        }

        if not self.token:
            raise GitHubConnectorError(
                "GITHUB_TOKEN is not configured. Set it in your local environment."
            )

        for repository in self.allowed_repositories:
            if not _REPOSITORY_PATTERN.fullmatch(repository):
                raise GitHubConnectorError(
                    "Repository allowlist entries must use the owner/repository format."
                )

        if not self.base_url.startswith(("https://",)):
            raise GitHubConnectorError("GitHub API URL must use HTTPS.")

        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.text-match+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubConnector":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def search_code(
        self,
        query: str,
        repositories: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, str]]:
        """Search approved repositories and return source links and matching snippets."""
        query = query.strip()
        if not query:
            raise ValueError("Search query must not be empty.")

        if not 1 <= max_results <= 10:
            raise ValueError("max_results must be between 1 and 10.")

        if not self.allowed_repositories:
            raise GitHubConnectorError(
                "No repositories are configured. Set GITHUB_ALLOWED_REPOSITORIES."
            )

        requested = repositories or sorted(self.allowed_repositories)
        normalized = {repository.lower() for repository in requested}

        if not normalized:
            raise ValueError("At least one repository must be selected.")

        unauthorized = normalized - self.allowed_repositories
        if unauthorized:
            raise GitHubConnectorError(
                "Search requested a repository outside the configured allowlist."
            )

        # Use GitHub's repo qualifier rather than accepting arbitrary query filters.
        search_query = " ".join(
            [query, *(f"repo:{repository}" for repository in sorted(normalized))]
        )

        try:
            response = self._client.get(
                f"{self.base_url}/search/code",
                params={"q": search_query, "per_page": max_results},
            )
        except httpx.TimeoutException as exc:
            raise GitHubConnectorError("GitHub code search timed out.") from exc
        except httpx.RequestError as exc:
            raise GitHubConnectorError(
                "Could not connect to the GitHub API."
            ) from exc

        if response.status_code == 401:
            raise GitHubConnectorError(
                "GitHub authentication failed. Check the token configuration."
            )
        if response.status_code == 403:
            raise GitHubConnectorError(
                "GitHub denied the request or the API rate limit was reached. "
                "Check token permissions and rate limits."
            )
        if response.status_code == 422:
            raise GitHubConnectorError(
                "GitHub rejected the search query. Try a simpler query."
            )
        if response.status_code >= 400:
            raise GitHubConnectorError(
                f"GitHub API returned HTTP {response.status_code}."
            )

        payload = response.json()
        results: list[dict[str, str]] = []

        for item in payload.get("items", []):
            repository = item.get("repository", {}).get("full_name", "")
            if repository.lower() not in self.allowed_repositories:
                continue

            matches = item.get("text_matches", [])
            snippets = [
                match.get("fragment", "")
                for match in matches
                if match.get("fragment")
            ]

            results.append(
                {
                    "repository": repository,
                    "path": item.get("path", ""),
                    "url": item.get("html_url", ""),
                    "snippet": "\n...\n".join(snippets)
                    or "No matching snippet was returned by GitHub.",
                }
            )

        return results
