"""Plotly figures shared by analyze.py and the Space.

Colors are the validated default categorical palette (dataviz reference instance,
first five slots, adjacent pairs pass CVD/normal-vision checks in both modes).
Three light-mode slots sit below 3:1 contrast, so every series is direct-labeled
and the Space also shows the table.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .client import EFFORTS

# fixed category -> color order; color follows the category, never its rank
CATEGORIES = ["math", "code", "tools", "tool_schema", "structured"]
LABELS = {"math": "Math", "code": "Code", "tools": "Tool calling", "tool_schema": "Tool schemas",
          "structured": "Structured output"}
LIGHT = {"math": "#2a78d6", "code": "#eb6834", "tools": "#1baf7a", "tool_schema": "#eda100", "structured": "#e87ba4"}
DARK = {"math": "#3987e5", "code": "#d95926", "tools": "#199e70", "tool_schema": "#c98500", "structured": "#d55181"}
THEME = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "grid": "#e8e7e3", "colors": LIGHT},
    "dark": {"surface": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "grid": "#33322f", "colors": DARK},
}


def _layout(fig, mode, title, height=460):
    t = THEME[mode]
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 16, "color": t["text"]}},
        paper_bgcolor=t["surface"], plot_bgcolor=t["surface"], height=height,
        font={"family": "Inter, system-ui, sans-serif", "size": 12, "color": t["muted"]},
        margin={"l": 56, "r": 120, "t": 64, "b": 48},
        legend={"orientation": "h", "y": -0.18, "x": 0, "font": {"color": t["text"]}},
        hoverlabel={"bgcolor": t["surface"], "font": {"color": t["text"]}},
    )
    fig.update_xaxes(gridcolor=t["grid"], zeroline=False, linecolor=t["grid"], tickfont={"color": t["muted"]})
    fig.update_yaxes(gridcolor=t["grid"], zeroline=False, linecolor=t["grid"], tickfont={"color": t["muted"]})
    return fig


def pareto(table, mode="light", cost_col="tokens_mean"):
    """Headline: accuracy vs tokens, one line per category through low..max."""
    t = THEME[mode]
    fig = go.Figure()
    ends = []
    for cat in CATEGORIES:
        d = table[table["category"] == cat].sort_values("effort")
        if d.empty:
            continue
        color = t["colors"][cat]
        fig.add_trace(go.Scatter(
            x=d[cost_col], y=d["acc"] * 100, mode="lines+markers", name=LABELS[cat],
            line={"color": color, "width": 2}, marker={"size": 9, "color": color, "line": {"width": 2, "color": t["surface"]}},
            customdata=d[["effort", "ci_lo", "ci_hi", "tasks"]].astype(str).values,
            hovertemplate=f"<b>{LABELS[cat]}</b> · %{{customdata[0]}}<br>accuracy %{{y:.1f}}% "
                          "(95% CI %{customdata[1]}–%{customdata[2]})<br>mean tokens %{x:,.0f}<extra></extra>",
        ))
        ends.append([d.iloc[-1]["acc"] * 100, cat])

    # direct labels in the right margin at each line's max-effort height, nudged apart
    ends.sort(reverse=True)
    for i in range(1, len(ends)):
        ends[i][0] = min(ends[i][0], ends[i - 1][0] - 6)
    for y, cat in ends:
        fig.add_annotation(xref="paper", x=1.01, y=y, xanchor="left", showarrow=False,
                           text=f"<span style='color:{t['colors'][cat]}'>●</span> {LABELS[cat]}",
                           font={"color": t["text"], "size": 11})

    lo = min(table[cost_col].min(), 100)
    hi = max(table[cost_col].max(), 1000)
    ticks = [v for v in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) if lo / 2 <= v <= hi * 2]
    fig.update_xaxes(title_text="Mean completion tokens per task (log scale)", type="log",
                     tickvals=ticks, ticktext=[f"{v // 1000}k" if v >= 1000 else str(v) for v in ticks])
    fig.update_yaxes(title_text="Accuracy (%)", range=[0, 105])
    fig = _layout(fig, mode, "Accuracy vs. tokens spent, each line runs low → max effort")
    fig.update_layout(margin={"r": 150})
    return fig


def by_effort(table, value, mode="light", title="", yaxis="", ci=False, percent=False):
    """Small multiples: one panel per category, effort on x. Single series per panel."""
    t = THEME[mode]
    cats = [c for c in CATEGORIES if c in set(table["category"])]
    fig = make_subplots(rows=1, cols=len(cats), shared_yaxes=True, subplot_titles=[LABELS[c] for c in cats],
                        horizontal_spacing=0.03)
    scale = 100 if percent else 1
    for i, cat in enumerate(cats, 1):
        d = table[table["category"] == cat].sort_values("effort")
        y = d[value] * scale
        err = None
        if ci:
            err = {"type": "data", "symmetric": False, "array": (d["ci_hi"] - d[value]) * scale,
                   "arrayminus": (d[value] - d["ci_lo"]) * scale, "color": t["colors"][cat], "thickness": 1.5, "width": 4}
        fig.add_trace(go.Scatter(
            x=d["effort"].astype(str), y=y, mode="lines+markers", name=LABELS[cat], showlegend=False, error_y=err,
            line={"color": t["colors"][cat], "width": 2}, marker={"size": 9, "color": t["colors"][cat]},
            hovertemplate=f"<b>{LABELS[cat]}</b> · %{{x}}<br>{yaxis} %{{y:,.1f}}<extra></extra>",
        ), row=1, col=i)
    for a in fig.layout.annotations:
        a.font = {"color": t["text"], "size": 12}
    fig.update_xaxes(categoryorder="array", categoryarray=EFFORTS)
    fig.update_yaxes(title_text=yaxis, row=1, col=1)
    if percent:
        fig.update_yaxes(range=[0, 105])  # a flat 100% must look flat, not zoomed
    else:
        fig.update_yaxes(rangemode="tozero")
    fig = _layout(fig, mode, title, height=360)
    fig.update_layout(margin={"r": 24})
    return fig
