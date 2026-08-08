"""Versioned prompt templates and their loader."""

from app.services.ai.prompts.loader import (
    EXECUTIVE_SUMMARY,
    PROMPT_VERSION,
    RECOMMENDATIONS,
    RISKS,
    ROOT_CAUSE,
    SYSTEM,
    load_prompt,
    render,
    system_prompt,
)

__all__ = [
    "EXECUTIVE_SUMMARY",
    "PROMPT_VERSION",
    "RECOMMENDATIONS",
    "RISKS",
    "ROOT_CAUSE",
    "SYSTEM",
    "load_prompt",
    "render",
    "system_prompt",
]
