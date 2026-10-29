"""Plotly figures used by the app. Kept separate so the engine has no UI dependencies."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

INK = "#0B1324"
MUTED = "#5B6B82"
GRID = "#EDF1F6"
AXIS = "#D5DCE6"
ACCENT = "#0D7A6F"
TOKENS = "#2B3A55"
GOOD = "#13804A"
WARN = "#B7791F"
BAD = "#C53030"
PAR = "#94A3B8"

VERDICT_COLORS = {"HOLDS": GOOD, "LIQUIDITY STRAIN": WARN, "BELOW PAR": "#C05621", "BREAKS": BAD}

FONT = dict(family="Inter, -apple-system, Segoe UI, Roboto, sans-serif", color=INK, size=12.5)


def _base(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="simple_white",
        height=height,
        font=FONT,
        margin=dict(l=8, r=8, t=76 if title else 16, b=8),
        title=dict(text=title, x=0.005, xanchor="left", y=1, yanchor="top", pad=dict(t=10),
                   font=dict(size=14, color=INK, weight=600)) if title else None,
        # legend sits on its own row between the title and the plot, so long titles never collide with it
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=11.5, color=MUTED),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT["family"], color=INK, size=12)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, ticks="", tickfont=dict(color=MUTED),
                     title_font=dict(color=MUTED, size=12))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, showline=False, ticks="", tickfont=dict(color=MUTED),
                     title_font=dict(color=MUTED, size=12), zeroline=False)
    return fig


def composition_donut(comp: pd.DataFrame, center_text: str = "") -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=comp["Asset class"], values=comp["Amount ($bn)"], hole=0.62, sort=False,
            marker=dict(colors=comp["color"], line=dict(color="white", width=2)),
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}bn<br>%{percent}<extra></extra>",
        )
    )
    fig.add_annotation(text=center_text, showarrow=False, font=dict(size=15, color=INK))
    fig = _base(fig, height=300)
    fig.update_layout(showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5, yanchor="middle", xanchor="left"),
                      margin=dict(l=0, r=0, t=10, b=10))
    return fig


def reserves_vs_tokens(daily: pd.DataFrame) -> go.Figure:
    short = bool((daily["reserves"] < daily["supply"] * 0.9995).any())
    fill = "rgba(197,48,48,0.10)" if short else "rgba(13,122,111,0.10)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["supply"], name="Tokens outstanding", mode="lines+markers",
                             line=dict(color=TOKENS, width=2, dash="dot"), marker=dict(size=6),
                             hovertemplate="Day %{x}<br>Tokens $%{y:,.2f}bn<extra></extra>"))
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["reserves"], name="Reserves (marked to market)",
                             mode="lines+markers", line=dict(color=ACCENT, width=3), marker=dict(size=7),
                             fill="tonexty", fillcolor=fill,
                             hovertemplate="Day %{x}<br>Reserves $%{y:,.2f}bn<extra></extra>"))
    fig = _base(fig, title="Reserves vs tokens outstanding ($bn)")
    fig.update_xaxes(title="Business day", dtick=1)
    return fig


def coverage_path(daily: pd.DataFrame) -> go.Figure:
    cov = daily["coverage"].astype(float)
    colors = [GOOD if c >= 0.9995 else BAD for c in cov.fillna(0)]
    fig = go.Figure()
    fig.add_hline(y=1.0, line=dict(color=PAR, dash="dash"), annotation_text="Par ($1.00)",
                  annotation_position="top left", annotation_font_color=MUTED)
    fig.add_trace(go.Scatter(x=daily["day"], y=cov, mode="lines+markers", name="Coverage",
                             line=dict(color=INK, width=2), marker=dict(size=8, color=colors),
                             hovertemplate="Day %{x}<br>Reserves per token $%{y:.4f}<extra></extra>"))
    fig = _base(fig, title="Reserves per token (coverage ratio)")
    lo = float(np.nanmin(cov)) if cov.notna().any() else 0.9
    hi = float(np.nanmax(cov)) if cov.notna().any() else 1.1
    fig.update_yaxes(range=[min(lo, 0.99) - 0.01, max(hi, 1.01) + 0.01], tickformat=".3f")
    fig.update_xaxes(title="Business day", dtick=1)
    fig.update_layout(showlegend=False)
    return fig


def redemptions_bars(daily: pd.DataFrame) -> go.Figure:
    d = daily[daily["day"] > 0]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d["day"], y=d["paid"], name="Paid at $1", marker_color=ACCENT,
                         hovertemplate="Day %{x}<br>Paid $%{y:,.2f}bn<extra></extra>"))
    fig.add_trace(go.Bar(x=d["day"], y=d["unmet"], name="Waiting (unmet)", marker_color=BAD,
                         hovertemplate="Day %{x}<br>Unmet $%{y:,.2f}bn<extra></extra>"))
    fig = _base(fig, title="Redemptions each day ($bn)")
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_xaxes(title="Business day", dtick=1)
    return fig


def loss_breakdown(summary: dict) -> go.Figure:
    items = [
        ("Rate shock (bills/notes)", summary["rate_loss"]),
        ("Price & credit shocks", summary["price_loss"]),
        ("Frozen bank cash written off", summary["frozen_writedown"]),
        ("Fire-sale discounts", summary["fire_sale_loss"]),
    ]
    df = pd.DataFrame(items, columns=["Source", "Loss"])
    fig = go.Figure(go.Bar(x=df["Loss"], y=df["Source"], orientation="h",
                           marker_color=["#7A4FD1", "#C77D12", "#2B59C3", BAD],
                           text=[f"${v:,.2f}bn" for v in df["Loss"]], textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}: $%{x:,.3f}bn<extra></extra>"))
    fig = _base(fig, height=260, title="Where the losses came from")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, max(df["Loss"].max() * 1.3, 0.01)])
    return fig


def holdings_used(by_holding: pd.DataFrame) -> go.Figure:
    d = by_holding.copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d["Holding"], x=d["End ($bn)"], name="Left", orientation="h", marker_color="#D5DCE6",
                         hovertemplate="%{y}<br>Left $%{x:,.2f}bn<extra></extra>"))
    fig.add_trace(go.Bar(y=d["Holding"], x=d["Sold ($bn)"], name="Sold to pay redemptions", orientation="h",
                         marker_color=ACCENT, hovertemplate="%{y}<br>Sold $%{x:,.2f}bn<extra></extra>"))
    lost = d["Rate loss ($bn)"] + d["Price/credit loss ($bn)"] + d["Frozen ($bn)"]
    fig.add_trace(go.Bar(y=d["Holding"], x=lost, name="Lost / frozen on day 0", orientation="h",
                         marker_color=BAD, hovertemplate="%{y}<br>Lost/frozen $%{x:,.2f}bn<extra></extra>"))
    fig = _base(fig, height=max(240, 46 * len(d) + 80), title="What each holding did ($bn)")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


def breaking_heatmap(grid: pd.DataFrame, frontier: pd.DataFrame | None = None,
                     marker: tuple[float, float] | None = None) -> go.Figure:
    pivot = grid.pivot(index="run_pct", columns="rate_shock_bp", values="min_coverage")
    late = grid.pivot(index="run_pct", columns="rate_shock_bp", values="late")
    z = pivot.values.astype(float)
    zc = np.clip(z, 0.80, 1.05)
    # diverging scale centred on par: red below 1.0, green at/above
    lo, hi = 0.80, 1.05
    mid = (1.0 - lo) / (hi - lo)
    scale = [[0.0, "#7F1D1D"], [mid * 0.5, "#DC2626"], [mid * 0.98, "#FCA5A5"], [mid, "#F8FAFC"],
             [min(mid + 0.02, 1), "#BBF7D0"], [1.0, "#15803D"]]
    text = np.where(late.values, "late", "")
    fig = go.Figure(go.Heatmap(
        z=zc, x=pivot.columns, y=pivot.index, zmin=lo, zmax=hi, colorscale=scale,
        customdata=np.dstack([z, late.values]),
        text=text, texttemplate="%{text}", textfont=dict(size=9, color="rgba(255,255,255,0.85)"),
        colorbar=dict(title=dict(text="Lowest<br>coverage", font=dict(size=12)), tickformat=".2f", len=0.85),
        hovertemplate="Rate shock +%{x:.0f}bp<br>Run %{y:.0f}% of supply<br>Lowest coverage %{customdata[0]:.4f}"
                      "<br>Paid late: %{customdata[1]}<extra></extra>",
    ))
    if frontier is not None and len(frontier):
        fig.add_trace(go.Scatter(x=frontier["rate_shock_bp"], y=frontier["max_run_paid_on_time"], mode="lines",
                                 line=dict(color=INK, width=2, dash="dash", shape="hv"),
                                 name="Largest run paid on time",
                                 hovertemplate="+%{x:.0f}bp: paid on time up to %{y:.0f}% run<extra></extra>"))
        fig.add_trace(go.Scatter(x=frontier["rate_shock_bp"], y=frontier["max_run_holds"], mode="lines",
                                 line=dict(color=INK, width=3, shape="hv"), name="Largest run that still holds",
                                 hovertemplate="+%{x:.0f}bp: survives up to %{y:.0f}% run<extra></extra>"))
    if marker:
        fig.add_trace(go.Scatter(x=[marker[0]], y=[marker[1]], mode="markers", name="Your scenario",
                                 marker=dict(symbol="x", size=16, color=INK, line=dict(width=2, color="white"))))
    fig = _base(fig, height=520, title="Where the peg breaks: lowest coverage by rate shock and run size")
    fig.update_xaxes(title="Parallel rate shock (bp)")
    fig.update_yaxes(title="Run size (% of supply asking to redeem)", showgrid=False)
    return fig


def liquidity_ladder(ladder: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=ladder["Days"].astype(str) + "d", y=ladder["Share of supply"],
                           marker_color=[GOOD if v >= 1 else ACCENT for v in ladder["Share of supply"]],
                           text=[f"{v:.0%}" for v in ladder["Share of supply"]], textposition="outside",
                           cliponaxis=False,
                           hovertemplate="Within %{x}: %{y:.1%} of supply<extra></extra>"))
    fig.add_hline(y=1.0, line=dict(color=PAR, dash="dash"), annotation_text="All tokens",
                  annotation_position="top left", annotation_font_color=MUTED)
    fig = _base(fig, height=300, title="Cash the issuer can raise within N business days")
    fig.update_yaxes(tickformat=".0%", range=[0, max(1.15, float(ladder["Share of supply"].max()) * 1.15)])
    return fig


def peg_history(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_hrect(y0=0.995, y1=1.005, fillcolor="rgba(19,128,74,0.07)", line_width=0,
                  annotation_text="±50bp", annotation_position="top left", annotation_font_color=MUTED)
    palette = [ACCENT, "#2B59C3", "#C77D12", "#7A4FD1", "#C2416B", "#5B6B82"]
    for i, (coin, g) in enumerate(df.groupby("coin")):
        fig.add_trace(go.Scatter(x=g["time"], y=g["price"], name=coin, mode="lines",
                                 line=dict(width=2, color=palette[i % len(palette)]),
                                 hovertemplate=f"{coin} %{{x|%d %b %Y}}: $%{{y:.4f}}<extra></extra>"))
    fig = _base(fig, height=360, title="Daily price vs the $1 peg")
    fig.update_yaxes(tickformat=".3f")
    return fig


def supply_bars(df: pd.DataFrame, n: int = 10) -> go.Figure:
    d = df.head(n)
    fig = go.Figure(go.Bar(x=d["supply_usd"] / 1e9, y=d["symbol"], orientation="h", marker_color=ACCENT,
                           text=[f"${v / 1e9:,.1f}bn" for v in d["supply_usd"]], textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}: $%{x:,.2f}bn<extra></extra>"))
    fig = _base(fig, height=max(240, 34 * len(d) + 60), title="Largest USD stablecoins by supply ($bn)")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, float(d["supply_usd"].max() / 1e9) * 1.3])
    return fig


def svb_episode(df: pd.DataFrame, nav_worst: float, nav_chosen: float, recovery: float) -> go.Figure:
    fig = go.Figure()
    fig.add_hline(y=1.0, line=dict(color=PAR, dash="dash"))
    fig.add_hline(y=nav_worst, line=dict(color=BAD, dash="dot", width=2),
                  annotation_text=f"Model: value per token if SVB cash is lost ({nav_worst:.3f})",
                  annotation_position="bottom right", annotation_font_color=BAD)
    if abs(nav_chosen - nav_worst) > 1e-4:
        fig.add_hline(y=nav_chosen, line=dict(color=ACCENT, dash="dot", width=2),
                      annotation_text=f"Model at {recovery:.0f}% recovery ({nav_chosen:.3f})",
                      annotation_position="top right", annotation_font_color=ACCENT)
    fig.add_trace(go.Scatter(x=df["time"], y=df["price"], mode="lines+markers", name="USDC market price",
                             line=dict(color=INK, width=3), marker=dict(size=6),
                             text=df.get("event"),
                             hovertemplate="%{x|%a %d %b %H:%M}<br>$%{y:.3f}<br>%{text}<extra></extra>"))
    i_low = int(df["price"].idxmin())
    fig.add_annotation(x=df.loc[i_low, "time"], y=df.loc[i_low, "price"], text=f"Low ${df.loc[i_low, 'price']:.2f}",
                       showarrow=True, arrowhead=0, ax=40, ay=20, font=dict(color=BAD))
    fig.add_vrect(x0="2023-03-11T00:00:00Z", x1="2023-03-13T00:00:00Z", fillcolor="rgba(100,116,139,0.08)",
                  line_width=0, annotation_text="Weekend: no redemptions via US banks",
                  annotation_position="top left", annotation_font_color=MUTED)
    fig = _base(fig, height=420, title="USDC around the Silicon Valley Bank weekend (March 2023)")
    fig.update_yaxes(tickformat=".2f", range=[0.84, 1.02])
    fig.update_layout(showlegend=False)
    return fig


def preset_frontier_bars(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=df["Largest run survived (%)"], y=df["Portfolio"], orientation="h",
                           marker_color=[GOOD if v >= 50 else (WARN if v >= 20 else BAD)
                                         for v in df["Largest run survived (%)"]],
                           text=[f"{v:.0f}%" for v in df["Largest run survived (%)"]], textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}: %{x:.0f}% run<extra></extra>"))
    fig = _base(fig, height=max(240, 50 * len(df) + 70), title="Largest run each portfolio survives at this rate shock")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(range=[0, 115], ticksuffix="%", showgrid=True, gridcolor=GRID)
    return fig
