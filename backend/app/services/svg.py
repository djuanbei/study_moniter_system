"""Diagram generation: SVG preferred, Mermaid optional.

Both formats are produced from a structured spec that the LLM emits:
  {
    "format": "svg" | "mermaid",
    "spec": {...}
  }

Security:
  - Only the whitelisted shape primitives below are rendered.
  - Every attribute value is XML-escaped; tag names come from a fixed set.
  - `style` / `on*` event handlers are explicitly stripped if present in the spec.
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Any


# --- SVG ---------------------------------------------------------------------

_ALLOWED_SHAPES = {"rect", "circle", "line", "polygon", "label"}
# Anything starting with "on" (event handlers) or equal to "style"/"script"/"href"
_FORBIDDEN_ATTRS = re.compile(r"^(on|style|script|href|xlink:href|formaction)$", re.IGNORECASE)
_SAFE_FILL_PATTERN = re.compile(r"^[#\w(),.% -]+$")  # CSS-color-ish values only
_SAFE_STROKE_PATTERN = _SAFE_FILL_PATTERN
_SAFE_ANCHOR_VALUES = {"start", "middle", "end"}


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _attr(name: str, value: Any, *, allow: re.Pattern | None = None,
          allowed_values: set[str] | None = None) -> str | None:
    """Return a sanitized attribute string, or None if the value is unsafe."""
    if _FORBIDDEN_ATTRS.match(str(name)):
        return None
    text = str(value)
    if allowed_values is not None and text not in allowed_values:
        return None
    if allow is not None and not allow.match(text):
        return None
    return f' {name}="{_xml_escape(text)}"'


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_svg(spec: dict[str, Any]) -> str:
    """Render a simple SVG diagram from a structured spec.

    Supported shapes: rectangle, circle, line, label, polygon. The intent is
    to give the LLM a deterministic, side-effect-free way to produce geometry
    diagrams without an external library. Unknown shape types are ignored; all
    attribute values are XML-escaped and whitelisted.
    """
    width = int(_num(spec.get("width", 480), 480))
    height = int(_num(spec.get("height", 320), 320))
    shapes = spec.get("shapes", []) or []
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
    ]

    for sh in shapes:
        if not isinstance(sh, dict):
            continue
        kind = sh.get("type")
        if kind not in _ALLOWED_SHAPES:
            continue  # unknown shape — silently skip
        if kind == "rect":
            attrs = (
                _attr("x", _num(sh.get("x"))) +
                _attr("y", _num(sh.get("y"))) +
                _attr("width", _num(sh.get("w"))) +
                _attr("height", _num(sh.get("h"))) +
                (_attr("fill", sh.get("fill", "none"), allow=_SAFE_FILL_PATTERN) or ' fill="none"') +
                (_attr("stroke", sh.get("stroke", "#333"), allow=_SAFE_STROKE_PATTERN) or ' stroke="#333"') +
                (_attr("stroke-width", sh.get("stroke_width", 1.5)) or ' stroke-width="1.5"')
            )
            parts.append(f"<rect{attrs}/>")
        elif kind == "circle":
            attrs = (
                _attr("cx", _num(sh.get("x"))) +
                _attr("cy", _num(sh.get("y"))) +
                _attr("r", _num(sh.get("r"))) +
                (_attr("fill", sh.get("fill", "none"), allow=_SAFE_FILL_PATTERN) or ' fill="none"') +
                (_attr("stroke", sh.get("stroke", "#333"), allow=_SAFE_STROKE_PATTERN) or ' stroke="#333"') +
                (_attr("stroke-width", sh.get("stroke_width", 1.5)) or ' stroke-width="1.5"')
            )
            parts.append(f"<circle{attrs}/>")
        elif kind == "line":
            attrs = (
                _attr("x1", _num(sh.get("x1"))) +
                _attr("y1", _num(sh.get("y1"))) +
                _attr("x2", _num(sh.get("x2"))) +
                _attr("y2", _num(sh.get("y2"))) +
                (_attr("stroke", sh.get("stroke", "#333"), allow=_SAFE_STROKE_PATTERN) or ' stroke="#333"') +
                (_attr("stroke-width", sh.get("stroke_width", 1.5)) or ' stroke-width="1.5"')
            )
            parts.append(f"<line{attrs}/>")
        elif kind == "polygon":
            pts = sh.get("points") or []
            coords = []
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    coords.append(f"{_num(p[0])},{_num(p[1])}")
            if not coords:
                continue
            attrs = (
                _attr("points", " ".join(coords)) +
                (_attr("fill", sh.get("fill", "none"), allow=_SAFE_FILL_PATTERN) or ' fill="none"') +
                (_attr("stroke", sh.get("stroke", "#333"), allow=_SAFE_STROKE_PATTERN) or ' stroke="#333"') +
                (_attr("stroke-width", sh.get("stroke_width", 1.5)) or ' stroke-width="1.5"')
            )
            parts.append(f"<polygon{attrs}/>")
        elif kind == "label":
            text = sh.get("text", "")
            if not isinstance(text, str):
                continue
            attrs = (
                _attr("x", _num(sh.get("x"))) +
                _attr("y", _num(sh.get("y"))) +
                (_attr("font-size", sh.get("size", 14)) or ' font-size="14"') +
                (_attr("fill", sh.get("fill", "#222"), allow=_SAFE_FILL_PATTERN) or ' fill="#222"') +
                (_attr("text-anchor", sh.get("anchor", "start"), allowed_values=_SAFE_ANCHOR_VALUES) or ' text-anchor="start"')
            )
            parts.append(f"<text{attrs}>{_xml_escape(text)}</text>")

    parts.append("</svg>")
    return "".join(parts)


# --- Mermaid -----------------------------------------------------------------

def render_mermaid(spec: dict[str, Any]) -> str:
    """Render a Mermaid diagram from a structured spec."""
    diagram_type = spec.get("diagram_type", "flowchart")
    code_lines = [f"{diagram_type} TD"]
    for node in spec.get("nodes", []):
        nid = node["id"]
        label = node.get("label", nid)
        code_lines.append(f"    {nid}[\"{label}\"]")
    for edge in spec.get("edges", []):
        src = edge["from"]
        dst = edge["to"]
        label = edge.get("label")
        if label:
            code_lines.append(f"    {src} -->|{label}| {dst}")
        else:
            code_lines.append(f"    {src} --> {dst}")
    return "\n".join(code_lines)


# --- LLM spec → diagram ------------------------------------------------------

def build_diagram_prompt(question_prompt: str) -> str:
    return textwrap.dedent(
        f"""
        You are a geometry diagram generator. Given the math question below,
        produce a JSON object describing either an SVG or Mermaid diagram.

        Question: {question_prompt}

        Return ONLY a JSON object with:
          - "format": "svg" or "mermaid"
          - "spec": the diagram spec

        For SVG use shapes: type=rect/circle/line/polygon/label with x, y, w/h, r, etc.
        For Mermaid use: diagram_type, nodes[{{id,label}}], edges[{{from,to,label?}}].
        """
    ).strip()


def diagram_from_json(text: str) -> tuple[str, str]:
    """Parse LLM text into (format, payload). Tolerant of code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    obj = json.loads(cleaned)
    fmt = obj.get("format", "svg")
    spec = obj.get("spec") or {}
    if fmt == "mermaid":
        return fmt, render_mermaid(spec)
    return fmt, render_svg(spec)