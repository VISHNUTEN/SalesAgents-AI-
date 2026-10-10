"""Prompt rendering utility (Step 6: load + safe variable substitution only)."""

from pathlib import Path
from typing import Any, Dict

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"

REQUIRED_VARIABLES = (
    "company_name",
    "customer_name",
    "agent_name",
    "agent_gender",
    "current_date",
    "current_day",
    "current_time",
    "additional_context_from_rag",
    "language_to_speak",
    "conversation_history",
    "customer_utterance",
)


def load_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def render_prompt(variables: Dict[str, Any]) -> str:
    rendered = load_template()
    for name in REQUIRED_VARIABLES:
        value = variables.get(name, "")
        rendered = rendered.replace("{{" + name + "}}", "" if value is None else str(value))
    return rendered
