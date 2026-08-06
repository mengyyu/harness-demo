"""Harness Admin — KPI Metric Cards."""

import streamlit as st


def render_kpi_row(metrics: list[dict], columns: int = 4):
    """Render a row of KPI metric cards.

    Args:
        metrics: List of dicts with 'label', 'value', and optional 'delta', 'help'.
        columns: Number of columns per row.
    """
    cols = st.columns(columns)
    for i, metric in enumerate(metrics):
        with cols[i % columns]:
            delta = metric.get("delta")
            help_text = metric.get("help")
            st.metric(
                label=metric["label"],
                value=metric["value"],
                delta=delta,
                help=help_text,
            )


def render_status_badge(status: str) -> str:
    """Return an emoji badge for a status string."""
    badges = {
        "success": "🟢",
        "failed": "🔴",
        "error": "🔴",
        "running": "🟡",
        "connected": "🟢",
        "disconnected": "🔴",
        "active": "🟢",
        "disabled": "⚫",
    }
    return badges.get(status, "⚪")
