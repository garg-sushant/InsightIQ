"""Prompt loading.

Prompts live in versioned markdown files beside this module, never as inline
strings, so they can be reviewed, diffed and rolled back independently of code.
The version is recorded on every persisted ``AIInsight``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.ai import AIPayload

PROMPT_DIR = Path(__file__).parent
PROMPT_VERSION = "v1"

SYSTEM = "system"
EXECUTIVE_SUMMARY = "executive_summary"
ROOT_CAUSE = "root_cause"
RECOMMENDATIONS = "recommendations"
RISKS = "risks"


@lru_cache(maxsize=16)
def load_prompt(name: str, version: str = PROMPT_VERSION) -> str:
    path = PROMPT_DIR / f"{name}.{version}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path.name}")
    return path.read_text(encoding="utf-8").strip()


def render(name: str, payload: AIPayload, version: str = PROMPT_VERSION) -> str:
    """Fill a template with the sanitised payload.

    ``str.replace`` rather than ``str.format``: the templates contain JSON
    schema examples full of literal braces, and formatting would choke on them.
    """
    template = load_prompt(name, version)
    serialised = json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=False)
    return template.replace("{payload}", serialised)


def system_prompt(version: str = PROMPT_VERSION) -> str:
    return load_prompt(SYSTEM, version)


__all__ = [
    "EXECUTIVE_SUMMARY",
    "PROMPT_DIR",
    "PROMPT_VERSION",
    "RECOMMENDATIONS",
    "RISKS",
    "ROOT_CAUSE",
    "SYSTEM",
    "load_prompt",
    "render",
    "system_prompt",
]
