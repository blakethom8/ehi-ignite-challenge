"""Engine-type badge component.

Four badge types:
  script   — 🔧 Script (deterministic)
  llm      — 🤖 LLM (AI extraction or judgment)
  table    — 📚 Reference table (frozen lookup)
  hybrid   — ⚙️ Hybrid
"""

import streamlit as st

_BADGE_STYLES = {
    "script": {
        "icon": "🔧",
        "label": "Script",
        "bg": "#1a3a1a",
        "border": "#2d6a2d",
        "color": "#7ec87e",
    },
    "llm": {
        "icon": "🤖",
        "label": "LLM",
        "bg": "#1a1a3a",
        "border": "#2d2d8a",
        "color": "#7e7eef",
    },
    "table": {
        "icon": "📚",
        "label": "Reference table",
        "bg": "#2a1a0a",
        "border": "#7a4a0a",
        "color": "#d4a44c",
    },
    "hybrid": {
        "icon": "⚙️",
        "label": "Hybrid",
        "bg": "#1a2a2a",
        "border": "#2a6a6a",
        "color": "#5ecece",
    },
}


def engine_badge(engine_type: str, detail: str = "") -> str:
    """Return an HTML string for a single engine-type badge.

    Parameters
    ----------
    engine_type : str
        One of "script", "llm", "table", "hybrid".
    detail : str
        Optional parenthetical note (e.g., "UMLS crosswalk").
    """
    style = _BADGE_STYLES.get(engine_type.lower(), _BADGE_STYLES["hybrid"])
    icon = style["icon"]
    label = style["label"]
    if detail:
        label = f"{label} ({detail})"
    bg = style["bg"]
    border = style["border"]
    color = style["color"]
    return (
        f'<span style="'
        f"background:{bg};"
        f"border:1px solid {border};"
        f"color:{color};"
        f"border-radius:4px;"
        f"padding:2px 8px;"
        f"font-size:0.78rem;"
        f"font-weight:600;"
        f"font-family:monospace;"
        f'white-space:nowrap;">'
        f"{icon} {label}"
        f"</span>"
    )


def engine_badge_row(badges: list[tuple[str, str]]) -> None:
    """Render a row of engine badges inline using st.markdown.

    Parameters
    ----------
    badges : list of (engine_type, detail) tuples
    """
    html_parts = [engine_badge(t, d) for t, d in badges]
    st.markdown(" &nbsp; ".join(html_parts), unsafe_allow_html=True)
