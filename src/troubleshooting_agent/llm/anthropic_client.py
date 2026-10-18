
import os

import anthropic
from dotenv import load_dotenv


load_dotenv()

MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-haiku-4-5-20251001",
)


def get_anthropic_client() -> anthropic.Anthropic:
    """Create an Anthropic client using the configured API key."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is missing. Configure it in .env."
        )

    return anthropic.Anthropic(api_key=api_key)


def test_connection() -> str:
    """Make a small request to verify the API configuration."""
    client = get_anthropic_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=64,
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: Anthropic connection successful",
            }
        ],
    )

    return response.content[0].text
