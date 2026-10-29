"""Shared state, sidebar, styling and formatting for every page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pegguard.analysis import STANDARD_SCENARIOS  # noqa: E402
from pegguard.charts import VERDICT_COLORS  # noqa: E402
from pegguard.engine import Scenario  # noqa: E402
from pegguard.presets import load_preset, preset_names  # noqa: E402
from pegguard.reserves import ASSET_CLASSES, frame_to_lines, lines_to_frame  # noqa: E402

DEFAULT_PRESET = "usdt_2026q2"

# Scenario widgets: session key -> default
SC_DEFAULTS = {
    "sc_rate": 200.0, "sc_run": 30.0, "sc_days": 5, "sc_front": 0.35,
    "sc_freeze": 0.0, "sc_recovery": 100.0, "sc_stress": 2.0,
    "sc_gold": 0.0, "sc_crypto": 0.0, "sc_risk": 0.0, "sc_loan": 0.0, "sc_panic": 0.0,
}

CSS = """
<style>
  :root {--pg-ink:#0B1324; --pg-muted:#5B6B82; --pg-line:#E3E8EF; --pg-card:#FFFFFF; --pg-accent:#0D7A6F;
         --pg-shadow: 0 1px 2px rgba(11,19,36,.04), 0 1px 3px rgba(11,19,36,.06);}
  .block-container {padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1280px;}
  header[data-testid="stHeader"] {background: transparent;}
  h1, h2, h3, h4 {letter-spacing: -0.015em;}
  [data-testid="stMarkdownContainer"] h2, [data-testid="stHeadingWithActionElements"] h2 {margin-top: .4rem;}
  hr {margin: 1.6rem 0 !important; border-color: var(--pg-line) !important;}

  /* page header */
  .pg-eyebrow {font-size: .72rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
               color: var(--pg-accent); margin-bottom: .35rem;}
  .pg-hero {font-size: 2.05rem; font-weight: 700; line-height: 1.18; margin: 0 0 .5rem 0; color: var(--pg-ink);
            letter-spacing: -0.025em;}
  .pg-sub {font-size: 1.02rem; line-height: 1.55; color: var(--pg-muted); max-width: 820px; margin-bottom: 1.6rem;}
  .pg-head {padding-bottom: .4rem; margin-bottom: 1.2rem; border-bottom: 1px solid var(--pg-line);}

  /* section labels */
  .pg-section {display:flex; align-items:baseline; gap:.6rem; margin: .2rem 0 .2rem 0;}
  .pg-section .t {font-size: 1.15rem; font-weight: 650; color: var(--pg-ink); letter-spacing: -0.01em;}
  .pg-section .n {font-size: .72rem; font-weight: 600; color: var(--pg-muted); letter-spacing: .1em;
                  text-transform: uppercase;}

  /* verdicts */
  .pg-banner {display:flex; align-items:center; gap:16px; background: var(--pg-card); border: 1px solid var(--pg-line);
              border-left: 5px solid; border-radius: 12px; padding: 16px 20px; margin: 4px 0 18px 0;
              box-shadow: var(--pg-shadow);}
  .pg-banner .v {font-size: 1.05rem; font-weight: 700; letter-spacing: .06em; white-space: nowrap;}
  .pg-banner .h {font-size: .98rem; color: var(--pg-ink); line-height: 1.45;}
  .pg-banner .lbl {font-size: .68rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
                   color: var(--pg-muted);}
  .pg-chip {display:inline-flex; align-items:center; gap:6px; padding: 3px 10px; border-radius: 999px;
            font-size: .72rem; font-weight: 650; letter-spacing: .04em; white-space: nowrap;}
  .pg-chip::before {content:""; width:6px; height:6px; border-radius:50%; background: currentColor;}

  /* cards */
  .pg-note {font-size: .85rem; color: var(--pg-muted); line-height: 1.5;}
  .pg-card {border: 1px solid var(--pg-line); border-radius: 12px; padding: 18px 20px; background: var(--pg-card);
            height: 100%; box-shadow: var(--pg-shadow);}
  .pg-card .k {font-size: .72rem; font-weight: 700; letter-spacing: .1em; color: var(--pg-accent);}
  .pg-card .t {font-size: 1rem; font-weight: 650; color: var(--pg-ink); margin: 4px 0 6px 0;}

  /* scorecard table */
  .pg-table {width:100%; border-collapse:separate; border-spacing:0; font-size:.88rem; background: var(--pg-card);
             border: 1px solid var(--pg-line); border-radius: 12px; overflow: hidden; box-shadow: var(--pg-shadow);}
  .pg-table th {text-align:center; padding:12px 10px; background:#F8FAFC; color: var(--pg-muted); font-weight:600;
                font-size:.76rem; line-height:1.35; border-bottom:1px solid var(--pg-line);}
  .pg-table th:first-child, .pg-table td:first-child {text-align:left; padding-left:18px;}
  .pg-table td {text-align:center; padding:12px 10px; border-bottom:1px solid #F0F3F7; vertical-align:middle;}
  .pg-table tr:last-child td {border-bottom:none;}
  .pg-table tr:hover td {background:#FAFBFD;}
  .pg-table td .val {font-size:.76rem; color: var(--pg-muted); margin-top:4px; font-variant-numeric: tabular-nums;}
  .pg-table td.name {font-weight:600; color: var(--pg-ink);}

  /* metrics */
  div[data-testid="stMetric"] {background: var(--pg-card); border: 1px solid var(--pg-line); border-radius: 12px;
                               padding: 14px 16px; box-shadow: var(--pg-shadow);}
  div[data-testid="stMetricLabel"] p {font-size: .74rem; font-weight: 600; color: var(--pg-muted);
                                      text-transform: uppercase; letter-spacing: .06em;}
  div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}

  /* charts, tables, expanders sit on white cards */
  div[data-testid="stPlotlyChart"] {background: var(--pg-card); border: 1px solid var(--pg-line); border-radius: 12px;
                                    padding: 8px 10px 4px 10px; box-shadow: var(--pg-shadow);}
  div[data-testid="stExpander"] details {background: var(--pg-card); border-color: var(--pg-line);}

  /* tabs */
  div[data-baseweb="tab-list"] {gap: 4px; border-bottom: 1px solid var(--pg-line);}
  button[data-baseweb="tab"] {padding: 10px 18px; font-weight: 600;}
  button[data-baseweb="tab"] p {font-size: .95rem;}

  /* sidebar */
  section[data-testid="stSidebar"] .pg-tag {font-size: .7rem; font-weight: 600; letter-spacing: .12em;
                                            text-transform: uppercase; color: #6F849C; margin: .2rem 0 .1rem 0;}
  section[data-testid="stSidebar"] .pg-side-card {border: 1px solid #1E3550; background: #10223A; border-radius: 10px;
                                                  padding: 12px 14px; margin-top: 4px;}
  section[data-testid="stSidebar"] .pg-side-card .row {display:flex; justify-content:space-between; align-items:baseline;
                                                       padding: 3px 0;}
  section[data-testid="stSidebar"] .pg-side-card .l {font-size: .78rem; color: #8FA3BA;}
  section[data-testid="stSidebar"] .pg-side-card .r {font-size: .98rem; font-weight: 650; color: #FFFFFF;
                                                     font-variant-numeric: tabular-nums;}
  section[data-testid="stSidebar"] .pg-foot {font-size: .72rem; color: #6F849C; line-height: 1.5;}
</style>
"""


# --------------------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------------------

def _load_into_state(preset_id: str) -> None:
    p = load_preset(preset_id)
    st.session_state.reserves_df = lines_to_frame(p.lines)
    st.session_state.supply = float(p.supply_bn)
    st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
    st.session_state.portfolio_meta = {"name": p.name, "description": p.description, "source": p.source,
                                       "as_of": p.as_of, "edited": False}


def init_state() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if "preset_id" not in st.session_state:
        st.session_state.preset_id = DEFAULT_PRESET
        _load_into_state(DEFAULT_PRESET)
    pending = st.session_state.pop("pending_preset", None)
    if pending:  # set by other pages; applied here before the sidebar widget exists
        st.session_state.preset_id = pending
        _load_into_state(pending)
    for k, v in SC_DEFAULTS.items():
        # Re-assigning keeps widget values alive when the user switches pages.
        st.session_state[k] = st.session_state.get(k, v)
    st.session_state.setdefault("live_data", False)


def on_preset_change() -> None:
    _load_into_state(st.session_state.preset_id)


def request_preset(preset_id: str) -> None:
    """Switch portfolio from inside a page (takes effect on the next rerun)."""
    st.session_state.pending_preset = preset_id


def apply_scenario(sc: Scenario) -> None:
    mapping = {
        "sc_rate": sc.rate_shock_bp, "sc_run": sc.redemption_pct, "sc_days": sc.horizon_days,
        "sc_front": sc.front_load, "sc_freeze": sc.bank_freeze_pct, "sc_recovery": sc.frozen_recovery_pct,
        "sc_stress": sc.stress_multiplier, "sc_gold": sc.gold_shock_pct, "sc_crypto": sc.crypto_shock_pct,
        "sc_risk": sc.risk_shock_pct, "sc_loan": sc.loan_loss_pct, "sc_panic": sc.panic_sensitivity,
    }
    for k, v in mapping.items():
        st.session_state[k] = type(SC_DEFAULTS[k])(v)


def current_scenario(name: str = "Your scenario") -> Scenario:
    s = st.session_state
    return Scenario(
        name=name, rate_shock_bp=float(s.sc_rate), redemption_pct=float(s.sc_run), horizon_days=int(s.sc_days),
        front_load=float(s.sc_front), bank_freeze_pct=float(s.sc_freeze), frozen_recovery_pct=float(s.sc_recovery),
        stress_multiplier=float(s.sc_stress), gold_shock_pct=float(s.sc_gold), crypto_shock_pct=float(s.sc_crypto),
        risk_shock_pct=float(s.sc_risk), loan_loss_pct=float(s.sc_loan), panic_sensitivity=float(s.sc_panic),
    )


def current_portfolio():
    lines = frame_to_lines(st.session_state.reserves_df)
    return lines, float(st.session_state.supply)


def portfolio_key() -> tuple:
    """Hashable fingerprint of the current portfolio for st.cache_data."""
    df = st.session_state.reserves_df
    return (tuple(map(tuple, df.astype(str).values.tolist())), round(float(st.session_state.supply), 6))


# --------------------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------------------

def sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="pg-tag">Workspace</div>', unsafe_allow_html=True)
        names = preset_names()
        st.selectbox("Reserve portfolio", options=list(names), format_func=names.get, key="preset_id",
                     on_change=on_preset_change)
        meta = st.session_state.portfolio_meta
        lines, supply = current_portfolio()
        reserves = sum(l.amount_bn for l in lines)
        backing = f"{reserves / supply:.2%}" if supply else "n/a"
        status = "Edited in the Stress Lab" if meta.get("edited") else f"As of {meta.get('as_of', '')}"
        st.markdown(
            f'<div class="pg-side-card">'
            f'<div class="row"><span class="l">Tokens outstanding</span><span class="r">${supply:,.2f}bn</span></div>'
            f'<div class="row"><span class="l">Reserves</span><span class="r">${reserves:,.2f}bn</span></div>'
            f'<div class="row"><span class="l">Backing ratio</span><span class="r">{backing}</span></div>'
            f'<div class="row"><span class="l">{status}</span></div></div>', unsafe_allow_html=True)
        st.divider()
        st.toggle("Fetch live market data", key="live_data",
                  help="Off = demo mode: uses cached / bundled data, so nothing depends on Wi-Fi.")
        st.markdown('<div class="pg-foot">NUS IS4228 · Technical track · Team Bulge<br>'
                    'Educational project, not investment or legal advice.</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------------------

def esc(text: str) -> str:
    """Escape dollar signs so Streamlit markdown does not render them as LaTeX maths."""
    return str(text).replace("$", "\\$")


def fmt_bn(x: float, dp: int = 2) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"${x:,.{dp}f}bn"


def fmt_cov(x: float) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.2%}"


def fmt_token(x: float) -> str:
    return "n/a" if x is None or pd.isna(x) else f"${x:.4f}"


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f'<div class="pg-sub">{subtitle}</div>' if subtitle else ""
    html = f'<div class="pg-eyebrow">{eyebrow}</div><div class="pg-hero">{title}</div>{sub}'
    # HTML entity so a pair of dollar signs is not rendered as LaTeX maths
    st.markdown(html.replace("$", "&#36;"), unsafe_allow_html=True)


def section(title: str, label: str = "") -> None:
    """Section heading with an optional small uppercase label (e.g. a step number)."""
    lbl = f'<span class="n">{label}</span>' if label else ""
    st.markdown(f'<div class="pg-section">{lbl}<span class="t">{title}</span></div>', unsafe_allow_html=True)


def verdict_banner(summary: dict) -> None:
    color = VERDICT_COLORS.get(summary["verdict"], "#334155")
    st.markdown(
        f'<div class="pg-banner" style="border-left-color:{color}">'
        f'<div><div class="lbl">Verdict</div><div class="v" style="color:{color}">{summary["verdict"]}</div></div>'
        f'<div class="h">{summary["headline"]}</div></div>',
        unsafe_allow_html=True,
    )


def verdict_chip(v: str) -> str:
    color = VERDICT_COLORS.get(v, "#334155")
    return f'<span class="pg-chip" style="color:{color}; background:{color}14; border:1px solid {color}33">{v}</span>'


def narrative(summary: dict, sc: Scenario, supply0: float) -> list[str]:
    s = summary
    out = []
    shocks = []
    if s["rate_loss"] > 1e-4:
        shocks.append(f"the +{sc.rate_shock_bp:.0f}bp rate rise cut {fmt_bn(s['rate_loss'])} off bills and notes")
    if s["price_loss"] > 1e-4:
        shocks.append(f"price and credit shocks cost {fmt_bn(s['price_loss'])}")
    if s["frozen"] > 1e-4:
        shocks.append(f"{fmt_bn(s['frozen'])} of bank cash was frozen "
                      f"({sc.frozen_recovery_pct:.0f}% assumed recoverable)")
    if shocks:
        out.append("**Day 0:** " + "; ".join(shocks) + f". Coverage moved from {fmt_cov(s['start_coverage'])} "
                   f"to {fmt_cov(s['day0_coverage'])}.")
    else:
        out.append(f"**Day 0:** no valuation shock. Coverage starts at {fmt_cov(s['start_coverage'])}.")
    out.append(f"**The run:** holders asked to redeem {fmt_bn(s['requested'])} over {sc.horizon_days} business days "
               f"and {fmt_bn(s['paid'])} was paid at $1.")
    if s["fire_sale_loss"] > 1e-4:
        out.append(f"**Selling in a hurry:** raising that cash cost {fmt_bn(s['fire_sale_loss'], 3)} in fire-sale "
                   "discounts.")
    if s["first_breach_day"] is not None:
        out.append(f"**Too slow:** from day {s['first_breach_day']} the issuer could not turn assets into cash fast "
                   f"enough. {fmt_bn(s['unmet'])} of redemptions were still waiting at the end.")
    if s["final_coverage"] < s["day0_coverage"] - 1e-4 and s["day0_coverage"] < 1:
        out.append(f"**First-mover advantage:** early redeemers got $1 while reserves were below par, so the "
                   f"{fmt_bn(s['supply_end'])} of tokens left are backed by only {fmt_token(s['final_coverage'])} "
                   f"each. That gap is why runs speed up (Diamond & Dybvig 1983).")
    elif s["verdict"] == "HOLDS":
        out.append(f"**Result:** reserves never dropped below par (lowest coverage {fmt_cov(s['min_coverage'])}).")
    return [esc(o) for o in out]


def scenario_library_options() -> dict[str, Scenario]:
    return {sc.name: sc for sc in STANDARD_SCENARIOS}


def asset_class_labels() -> list[str]:
    return [a.label for a in ASSET_CLASSES.values()]
