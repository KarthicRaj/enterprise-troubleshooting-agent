
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_FILE = PROJECT_ROOT / "SKILLS.md"


def load_agent_instructions() -> str:
    """Load the troubleshooting agent's role and behavioral rules."""
    if not SKILLS_FILE.exists():
        raise FileNotFoundError(
            f"Agent instructions not found: {SKILLS_FILE}"
        )

    return SKILLS_FILE.read_text(encoding="utf-8")
