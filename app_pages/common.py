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
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1300px;}
  h1, h2, h3 {letter-spacing: -0.01em;}
  .pg-hero {font-size: 2.1rem; font-weight: 700; margin: 0 0 .2rem 0; color: #0F172A;}
  .pg-sub {font-size: 1.05rem; color: #475569; margin-bottom: 1.2rem;}
  .pg-banner {border-radius: 12px; padding: 14px 18px; margin: 6px 0 14px 0; color: white;}
  .pg-banner .v {font-size: 1.25rem; font-weight: 700; letter-spacing: .02em;}
  .pg-banner .h {font-size: .98rem; opacity: .95; margin-top: 2px;}
  .pg-chip {display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
            color: white; white-space: nowrap;}
  .pg-note {font-size: .85rem; color: #64748B;}
  .pg-card {border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px; background: #FFFFFF; height: 100%;}
  .pg-card b {color:#0F172A;}
  div[data-testid="stMetric"] {background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
                               padding: 10px 14px;}
  div[data-testid="stMetricLabel"] p {font-size: .82rem; color: #475569;}
  section[data-testid="stSidebar"] .pg-brand {font-size: 1.35rem; font-weight: 800; color: #0F766E;}
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
        st.markdown('<div class="pg-brand">PegGuard</div>', unsafe_allow_html=True)
        st.caption("Stablecoin reserve stress tester")
        names = preset_names()
        st.selectbox("Reserve portfolio", options=list(names), format_func=names.get, key="preset_id",
                     on_change=on_preset_change)
        meta = st.session_state.portfolio_meta
        lines, supply = current_portfolio()
        reserves = sum(l.amount_bn for l in lines)
        backing = f"{reserves / supply:.2%}" if supply else "n/a"
        st.markdown(
            f'<div class="pg-card" style="padding:10px 12px"><span class="pg-note">Tokens outstanding</span><br>'
            f'<b style="font-size:1.15rem">${supply:,.2f}bn</b><br><span class="pg-note">Reserves / tokens</span><br>'
            f'<b style="font-size:1.15rem">{backing}</b></div>', unsafe_allow_html=True)
        if meta.get("edited"):
            st.caption("Edited in the Stress Lab")
        st.caption(f"As of: {meta.get('as_of', '')}")
        st.divider()
        st.toggle("Fetch live market data", key="live_data",
                  help="Off = demo mode: uses cached / bundled data, so nothing depends on Wi-Fi.")
        st.caption("NUS IS4228 · Technical track · Team Bulge")


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


def verdict_banner(summary: dict) -> None:
    color = VERDICT_COLORS.get(summary["verdict"], "#334155")
    st.markdown(
        f'<div class="pg-banner" style="background:{color}"><div class="v">{summary["verdict"]}</div>'
        f'<div class="h">{summary["headline"]}</div></div>',
        unsafe_allow_html=True,
    )


def verdict_chip(v: str) -> str:
    return f'<span class="pg-chip" style="background:{VERDICT_COLORS.get(v, "#334155")}">{v}</span>'


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
