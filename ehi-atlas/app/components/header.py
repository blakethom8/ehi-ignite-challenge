"""Consistent page header for every EHI Atlas Console page."""

import streamlit as st


_HEADER_CSS = """
<style>
.ehi-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 0 14px 0;
    border-bottom: 1px solid #333;
    margin-bottom: 20px;
}
.ehi-brand-mark {
    background: linear-gradient(135deg, #1a6aab, #0d3d6b);
    color: #e0f0ff;
    font-weight: 800;
    font-size: 1.1rem;
    font-family: monospace;
    padding: 4px 10px;
    border-radius: 5px;
    letter-spacing: 1px;
    border: 1px solid #2a8adb;
}
.ehi-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #ddeeff;
    margin: 0;
}
.ehi-subtitle {
    font-size: 0.8rem;
    color: #778899;
    margin: 2px 0 0 0;
}
.ehi-wip-flag {
    background: #2a1a05;
    border: 1px solid #7a5200;
    color: #d4a200;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 0.5px;
    white-space: nowrap;
    margin-left: auto;
}
</style>
"""


def render_header(page_title: str) -> None:
    """Render the standard EHI Atlas Console header.

    Call this at the top of every page, after st.set_page_config().

    Parameters
    ----------
    page_title : str
        The current page name (e.g. "Overview", "Sources & Bronze").
    """
    st.markdown(_HEADER_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ehi-header">
  <div class="ehi-brand-mark">EA</div>
  <div>
    <div class="ehi-title">EHI Atlas Console</div>
    <div class="ehi-subtitle">v0.1 &nbsp;·&nbsp; {page_title}</div>
  </div>
  <div class="ehi-wip-flag">WORKING NAME</div>
</div>
""",
        unsafe_allow_html=True,
    )
