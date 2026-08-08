"""Minimal markdown -> plain/rich text conversion for report embedding.

The AI sections come back as light markdown. ReportLab's paragraph parser wants
a small HTML-ish subset and python-pptx wants plain runs, so both need a
conversion step. This handles exactly the constructs the prompts ask for —
bold, italics, bullets and headings — and deliberately nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_ITALIC = re.compile(r"(?<![\w*])[*_]([^*_\n]+?)[*_](?![\w*])")
_CODE = re.compile(r"`([^`]+)`")
_BULLET = re.compile(r"^\s*[-*+]\s+")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+")
_HEADING = re.compile(r"^\s*#{1,6}\s+")


@dataclass(frozen=True)
class TextBlock:
    kind: str  # "paragraph" | "bullet" | "heading"
    text: str


def to_blocks(markdown: str) -> list[TextBlock]:
    """Split markdown into typed blocks, preserving inline emphasis markers."""
    blocks: list[TextBlock] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if _HEADING.match(line):
            blocks.append(TextBlock("heading", _HEADING.sub("", line).strip()))
        elif _BULLET.match(line):
            blocks.append(TextBlock("bullet", _BULLET.sub("", line).strip()))
        elif _NUMBERED.match(line):
            blocks.append(TextBlock("bullet", _NUMBERED.sub("", line).strip()))
        else:
            blocks.append(TextBlock("paragraph", line.strip()))
    return blocks


def to_reportlab(text: str) -> str:
    """Inline markdown -> the small HTML subset ReportLab's Paragraph accepts.

    Escaping happens *before* tags are introduced, so user- or model-supplied
    angle brackets can never inject markup into the PDF.
    """
    safe = escape(text, quote=False)
    safe = _BOLD.sub(r"<b>\1</b>", safe)
    safe = _ITALIC.sub(r"<i>\1</i>", safe)
    safe = _CODE.sub(r"<font face='Courier'>\1</font>", safe)
    return safe


def to_plain(text: str) -> str:
    """Strip all markdown markers, for PPTX text frames."""
    plain = _BOLD.sub(r"\1", text)
    plain = _ITALIC.sub(r"\1", plain)
    plain = _CODE.sub(r"\1", plain)
    plain = _HEADING.sub("", plain)
    return plain.strip()


def plain_bullets(markdown: str, *, limit: int = 8, max_chars: int = 240) -> list[str]:
    """Extract slide-ready bullet text from a markdown section."""
    bullets: list[str] = []
    for block in to_blocks(markdown):
        if block.kind == "heading":
            continue
        text = to_plain(block.text)
        # Drop the mock provider's italic disclaimer line from slide bodies;
        # the deck carries that notice once, on its own labelled slide.
        if text.startswith("_") or not text:
            continue
        bullets.append(text if len(text) <= max_chars else text[: max_chars - 1] + "…")
        if len(bullets) >= limit:
            break
    return bullets


__all__ = ["TextBlock", "plain_bullets", "to_blocks", "to_plain", "to_reportlab"]
