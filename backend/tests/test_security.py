"""Security-focused tests (PRD §85)."""

from __future__ import annotations

from app.main import FRONTEND_DIST

# The SPA fallback handler is registered at module level when dist exists.
from app.main import spa_fallback  # noqa: F401  (existence check via import)


def test_spa_fallback_blocks_absolute_path():
    resp = spa_fallback("/etc/passwd")
    assert "index.html" in str(resp.path)


def test_spa_fallback_blocks_dot_segments():
    for evil in ("assets/../../.env", "../.env", "data/../../.env"):
        resp = spa_fallback(evil)
        assert "index.html" in str(resp.path), evil


def test_spa_fallback_serves_static_and_fallback():
    legit = spa_fallback("index.html")
    assert str(legit.path) == str(FRONTEND_DIST / "index.html")
    missing = spa_fallback("no/such/route.css")
    assert "index.html" in str(missing.path)


def test_svg_sanitizer_stops_xss():
    from app.services.svg import sanitize_diagram_payload, sanitize_svg_markup

    evil = (
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        '<script>alert(1)</script>'
        '<circle cx="10" cy="10" r="5" fill="javascript:alert(1)"/>'
        '<text x="1" y="2">hi</text>'
        "</svg>"
    )
    clean = sanitize_svg_markup(evil)
    assert clean is not None
    assert "script" not in clean.lower()
    assert "onload" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert "<circle" in clean and "<text" in clean

    # broken / non-svg markup is dropped entirely
    assert sanitize_svg_markup("not xml <") is None
    assert sanitize_svg_markup("<html><body>x</body></html>") is None
    assert sanitize_diagram_payload("svg", "<svg></svg>")[1] is not None
    assert sanitize_diagram_payload("mermaid", "flowchart TD\n A-->B")[0] == "mermaid"
    assert sanitize_diagram_payload("svg", None) == (None, None)
