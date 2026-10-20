
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


class SplunkConnectorError(RuntimeError):
    """Raised when a Splunk request fails or is unsafe to execute."""


class SplunkConnector:
    """Read-only client for searching Splunk events."""

    def __init__(self) -> None:
        self.base_url = os.getenv("SPLUNK_BASE_URL", "").rstrip("/")
        self.token = os.getenv("SPLUNK_TOKEN", "")
        self.indexes = [
            item.strip()
            for item in os.getenv("SPLUNK_INDEXES", "").split(",")
            if item.strip()
        ]
        self.sourcetypes = [
            item.strip()
            for item in os.getenv("SPLUNK_SOURCETYPES", "").split(",")
            if item.strip()
        ]
        self.max_results = int(os.getenv("SPLUNK_MAX_RESULTS", "100"))
        self.lookback_minutes = int(
            os.getenv("SPLUNK_LOOKBACK_MINUTES", "60")
        )
        self.verify_tls = (
            os.getenv("SPLUNK_VERIFY_TLS", "true").lower() == "true"
        )

        if not self.base_url.startswith("https://"):
            raise SplunkConnectorError(
                "SPLUNK_BASE_URL must use HTTPS."
            )

        if not self.token:
            raise SplunkConnectorError(
                "SPLUNK_TOKEN is missing. Configure it in .env."
            )

        if not self.indexes:
            raise SplunkConnectorError(
                "Configure at least one approved SPLUNK_INDEXES value."
            )

        if not self.verify_tls:
            raise SplunkConnectorError(
                "TLS verification must remain enabled."
            )

        if not 1 <= self.max_results <= 500:
            raise SplunkConnectorError(
                "SPLUNK_MAX_RESULTS must be between 1 and 500."
            )

        if not 1 <= self.lookback_minutes <= 1440:
            raise SplunkConnectorError(
                "SPLUNK_LOOKBACK_MINUTES must be between 1 and 1440."
            )

        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
            verify=True,
            timeout=httpx.Timeout(15.0, read=30.0),
        )

       
    def search_logs(self, query: str) -> list[dict]:
        """Run a bounded, read-only search against approved indexes."""
        import json

        if not query or not query.strip():
            raise SplunkConnectorError("Search query cannot be empty.")

        if len(query) > 200 or any(
            char in query for char in "\r\n;|{}"
        ):
            raise SplunkConnectorError(
                "Search query contains unsupported characters."
            )

        escaped = query.replace("\\", "\\\\").replace('"', '\\"')

        index_filter = " OR ".join(
            f'index="{index.replace(chr(34), "")}"'
            for index in self.indexes
        )
        search = f'search ({index_filter}) "{escaped}"'

        if self.sourcetypes:
            sourcetype_filter = " OR ".join(
                f'sourcetype="{item.replace(chr(34), "")}"'
                for item in self.sourcetypes
            )
            search += f" AND ({sourcetype_filter})"

        # Bound the number of returned events in SPL as well as in Python.
        search += f" | head {self.max_results}"

        try:
            response = self.client.post(
                "/services/search/jobs/export",
                data={
                    "search": search,
                    "earliest_time": f"-{self.lookback_minutes}m",
                    "latest_time": "now",
                    "output_mode": "json",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise SplunkConnectorError(
                "Splunk search failed. Check connectivity, permissions, "
                "and server logs."
            ) from None

        events = []
        try:
            for line in response.text.splitlines():
                if not line.strip():
                    continue

                record = json.loads(line)
                event = record.get("result")

                if isinstance(event, dict):
                    events.append(event)

                if len(events) >= self.max_results:
                    break
        except (ValueError, AttributeError):
            raise SplunkConnectorError(
                "Splunk returned an unexpected export response."
            ) from None

        return events


    def close(self) -> None:
        self.client.close()
