"""Overview: what PegGuard does, a scorecard of every bundled portfolio, and the live stablecoin market."""

import pandas as pd
import streamlit as st

from app_pages.common import current_portfolio, esc, page_header, section, verdict_chip
from app_pages.live_monitor import render as live_monitor
from pegguard.analysis import STANDARD_SCENARIOS, regulatory_check, risk_profile, run_library
from pegguard.presets import all_presets

page_header(
    "Stablecoin reserve stress testing",
    "Will this stablecoin still be worth $1 when everyone wants out?",
    "PegGuard stress-tests a fiat-backed stablecoin's reserves. Pick a reserve portfolio, hit it with a rate shock, "
    "a bank failure or a crypto crash, start a run, and see day by day whether the issuer can still pay every token "
    "holder $1.")

c = st.columns(3)
cards = [
    ("01", "Reserves", "Load a real issuer's reported reserve mix (USDT, USDC) or build your own: cash, repo, "
                       "money market funds, T-bills, notes, gold, bitcoin, loans."),
    ("02", "Shock and run", "Day 0: rates jump, a bank fails, crypto crashes. Days 1-N: holders redeem and the issuer "
                            "sells assets through a liquidity waterfall, paying fire-sale discounts."),
    ("03", "Verdict", "Coverage ratio, value per token, unmet redemptions and the exact run size where the peg "
                      "breaks. Plus a GENIUS Act / MAS reserve-eligibility check."),
]
for col, (k, t, body) in zip(c, cards):
    col.markdown(f'<div class="pg-card"><div class="k">{k}</div><div class="t">{t}</div>'
                 f'<div class="pg-note">{body}</div></div>', unsafe_allow_html=True)

st.divider()
section("Every portfolio under the same five scenarios", "Scorecard")
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
html = ['<table class="pg-table"><tr><th>Portfolio</th>']
for sc in STANDARD_SCENARIOS:
    html.append(f"<th>{sc.name}</th>")
html.append("</tr>")
for i in range(len(verdicts)):
    html.append(f'<tr><td class="name">{verdicts.iloc[i]["Portfolio"]}</td>')
    for sc in STANDARD_SCENARIOS:
        v = verdicts.iloc[i][sc.name]
        val = values.iloc[i][sc.name]
        html.append(f'<td>{verdict_chip(v)}<div class="val">&#36;{val:.3f} / token</div></td>')
    html.append("</tr>")
html.append("</table>")
st.markdown("".join(html), unsafe_allow_html=True)
st.caption("Value per token = lowest reserves per token outstanding during the scenario. "
           "HOLDS: paid on time and at par · LIQUIDITY STRAIN: solvent but too slow · "
           "BELOW PAR: paid, but reserves < tokens · BREAKS: both.")

st.divider()
section(st.session_state.portfolio_meta["name"], "Selected portfolio")
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
k[4].metric("GENIUS eligible", f"{rc['GENIUS']['eligible_backing']:.0%}",
            help="Eligible reserve assets / tokens. Needs to be at least 100%.")
st.caption(esc(st.session_state.portfolio_meta.get("source", "")))

st.divider()
live_monitor()
