"""Overview: what PegGuard does, a scorecard of every bundled portfolio, and the live stablecoin market."""

import pandas as pd
import streamlit as st

from app_pages.common import current_portfolio, esc, fmt_bn, verdict_chip
from app_pages.live_monitor import render as live_monitor
from pegguard.analysis import STANDARD_SCENARIOS, regulatory_check, risk_profile, run_library
from pegguard.presets import all_presets

st.markdown('<div class="pg-hero">Will this stablecoin still be worth $1 when everyone wants out?</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="pg-sub">PegGuard stress-tests a fiat-backed stablecoin\'s reserves. Pick a reserve portfolio, '
    'hit it with a rate shock, a bank failure or a crypto crash, start a run, and see day by day whether the issuer '
    'can still pay every token holder $1.</div>', unsafe_allow_html=True)

c = st.columns(3)
cards = [
    ("1. Reserves", "Load a real issuer's reported reserve mix (USDT, USDC) or build your own: cash, repo, "
                    "money market funds, T-bills, notes, gold, bitcoin, loans."),
    ("2. Shock + run", "Day 0: rates jump, a bank fails, crypto crashes. Days 1-N: holders redeem and the issuer "
                       "sells assets through a liquidity waterfall, paying fire-sale discounts."),
    ("3. Verdict", "Coverage ratio, value per token, unmet redemptions and the exact run size where the peg "
                   "breaks. Plus a GENIUS Act / MAS reserve-eligibility check."),
]
for col, (t, body) in zip(c, cards):
    col.markdown(f'<div class="pg-card"><b>{t}</b><br><span class="pg-note">{body}</span></div>',
                 unsafe_allow_html=True)

st.write("")
st.subheader("Scorecard: every portfolio under the same five scenarios")
st.caption("Same shocks, same assumptions, so portfolios can be compared like for like. "
           "Open the Stress Lab to change any assumption.")


@st.cache_data(show_spinner=False)
def scorecard() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, cov_rows = [], []
    for p in all_presets():
        lib = run_library(p.lines, p.supply_bn)
        row = {"Portfolio": p.name}
        crow = {"Portfolio": p.name}
        for _, r in lib.iterrows():
            row[r["Scenario"]] = r["Verdict"]
            crow[r["Scenario"]] = r["Value per token"]
        rows.append(row)
        cov_rows.append(crow)
    return pd.DataFrame(rows), pd.DataFrame(cov_rows)


verdicts, values = scorecard()
html = ['<table style="width:100%; border-collapse:collapse; font-size:.9rem">', "<tr>"]
html.append('<th style="text-align:left; padding:8px; border-bottom:2px solid #E2E8F0">Portfolio</th>')
for sc in STANDARD_SCENARIOS:
    html.append(f'<th style="text-align:center; padding:8px; border-bottom:2px solid #E2E8F0; '
                f'color:#475569; font-weight:600">{sc.name}</th>')
html.append("</tr>")
for i in range(len(verdicts)):
    html.append("<tr>")
    html.append(f'<td style="padding:8px; border-bottom:1px solid #F1F5F9; font-weight:600">'
                f'{verdicts.iloc[i]["Portfolio"]}</td>')
    for sc in STANDARD_SCENARIOS:
        v = verdicts.iloc[i][sc.name]
        val = values.iloc[i][sc.name]
        html.append(f'<td style="text-align:center; padding:8px; border-bottom:1px solid #F1F5F9">'
                    f'{verdict_chip(v)}<div class="pg-note">${val:.3f}/token</div></td>')
    html.append("</tr>")
html.append("</table>")
st.markdown("".join(html), unsafe_allow_html=True)
st.caption("Value per token = lowest reserves per token outstanding during the scenario. "
           "HOLDS: paid on time and at par · LIQUIDITY STRAIN: solvent but too slow · "
           "BELOW PAR: paid, but reserves < tokens · BREAKS: both.")

st.divider()
st.subheader(f"Selected portfolio: {st.session_state.portfolio_meta['name']}")
lines, supply = current_portfolio()
rp = risk_profile(lines, supply)
rc = regulatory_check(lines, supply)
reserves = sum(l.amount_bn for l in lines)
k = st.columns(5)
k[0].metric("Backing ratio", f"{reserves / supply:.2%}", help="Reserves / tokens outstanding, before any shock")
k[1].metric("Rate sensitivity", f"{rp['loss_per_100bp_pct']:.2f}%",
            help="Approximate % of reserves lost if yields rise 100bp (modified duration)")
k[2].metric("Cash in 1 day", f"{rp['day1_capacity_share']:.0%}", help="Share of tokens that could be paid tomorrow")
k[3].metric("Cash in 5 days", f"{rp['day5_capacity_share']:.0%}",
            help="MAS requires par redemption within 5 business days")
k[4].metric("GENIUS-eligible backing", f"{rc['GENIUS']['eligible_backing']:.0%}",
            help="Eligible reserve assets / tokens. Needs to be at least 100%.")
st.caption(esc(st.session_state.portfolio_meta.get("source", "")))

st.divider()
live_monitor()
