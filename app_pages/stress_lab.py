"""Stress Lab: the core mechanic. Edit reserves, set a scenario, watch the run play out."""

import pandas as pd
import streamlit as st

from app_pages.common import (apply_scenario, esc, asset_class_labels, current_portfolio, current_scenario, fmt_bn,
                              fmt_cov, fmt_token, narrative, scenario_library_options, verdict_banner)
from pegguard import charts
from pegguard.engine import run_stress
from pegguard.reserves import composition

st.markdown('<div class="pg-hero">Stress Lab</div>', unsafe_allow_html=True)
st.markdown('<div class="pg-sub">Set the shock, start the run, and see whether every token still gets its $1.</div>',
            unsafe_allow_html=True)

meta = st.session_state.portfolio_meta

# ---------------------------------------------------------------- reserves -------------
lines, supply = current_portfolio()
reserves = sum(l.amount_bn for l in lines)
left, right = st.columns([1.35, 1])
with left:
    st.subheader(meta["name"])
    st.caption(esc(meta.get("description", "")))
    with st.expander("Edit reserves", expanded=False, icon=":material/edit:"):
        with st.form(f"reserve_form_{st.session_state.editor_version}", border=False):
            edited = st.data_editor(
                st.session_state.reserves_df,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                key=f"editor_{st.session_state.editor_version}",
                column_config={
                    "Holding": st.column_config.TextColumn(width="medium"),
                    "Asset class": st.column_config.SelectboxColumn(options=asset_class_labels(), required=True,
                                                                    width="medium"),
                    "Amount ($bn)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                    "Maturity (yrs)": st.column_config.NumberColumn(
                        min_value=0.0, max_value=30.0, format="%.3f",
                        help="0 for cash; 0.25 = 3-month bill; 10 = 10-year note"),
                    "Yield (%)": st.column_config.NumberColumn(min_value=-1.0, max_value=20.0, format="%.2f"),
                },
            )
            new_supply = st.number_input("Tokens outstanding ($bn)", min_value=0.01,
                                         value=float(st.session_state.supply), step=1.0, format="%.2f")
            if st.form_submit_button("Apply changes", type="primary", icon=":material/check:"):
                st.session_state.reserves_df = pd.DataFrame(edited).reset_index(drop=True)
                st.session_state.supply = float(new_supply)
                st.session_state.editor_version += 1
                st.session_state.portfolio_meta = {**meta, "edited": True}
                st.rerun()
        st.caption(esc(f"Source: {meta.get('source', '')}"))
with right:
    comp = composition(lines)
    st.plotly_chart(charts.composition_donut(comp, f"{fmt_bn(reserves, 1)}<br>reserves"),
                    width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------- scenario -------------
st.divider()
st.subheader("Scenario")
lib = scenario_library_options()
c0, c00 = st.columns([2, 1])
with c0:
    choice = st.selectbox("Start from a standard scenario (optional)", ["(keep my settings)"] + list(lib),
                          key="lab_preset_scenario")
with c00:
    st.write("")
    st.write("")
    if st.button("Load scenario", disabled=choice == "(keep my settings)", icon=":material/download:"):
        apply_scenario(lib[choice])
        st.rerun()

c1, c2, c3 = st.columns(3)
with c1:
    st.slider("Interest-rate shock (bp)", -100.0, 500.0, step=25.0, key="sc_rate",
              help="Instant parallel rise in yields. Reprices bills and notes (Week 3 bond maths).")
with c2:
    st.slider("Run size (% of tokens asking to redeem)", 0.0, 100.0, step=5.0, key="sc_run")
with c3:
    st.slider("Run length (business days)", 1, 20, key="sc_days",
              help="MAS requires par redemption within 5 business days.")

with st.expander("More shocks: bank failure, crypto crash, fire sales, panic", icon=":material/tune:"):
    a1, a2, a3 = st.columns(3)
    with a1:
        st.slider("Bank cash frozen in a bank failure (%)", 0.0, 100.0, step=5.0, key="sc_freeze",
                  help="Share of the reserves' bank deposits stuck at a failed bank (USDC had $3.3bn at SVB).")
        st.slider("Expected recovery on frozen cash (%)", 0.0, 100.0, step=5.0, key="sc_recovery")
        st.slider("How front-loaded the run is", 0.0, 0.9, step=0.05, key="sc_front",
                  help="0 = spread evenly; 0.5 = each day's requests are half the previous day's.")
    with a2:
        st.slider("Bitcoin / crypto price change (%)", -90.0, 0.0, step=5.0, key="sc_crypto")
        st.slider("Gold price change (%)", -50.0, 10.0, step=5.0, key="sc_gold")
        st.slider("Equities / other investments change (%)", -80.0, 10.0, step=5.0, key="sc_risk")
    with a3:
        st.slider("Credit loss on secured loans (%)", 0.0, 100.0, step=5.0, key="sc_loan")
        st.slider("Fire-sale stress multiplier", 0.0, 10.0, step=0.5, key="sc_stress",
                  help="Scales every asset's fire-sale discount. 1 = orderly market, 3+ = crisis.")
        st.slider("Panic feedback", 0.0, 1.0, step=0.05, key="sc_panic",
                  help="Extra redemptions for each 1pp that reserves fall below par. 0.2 = +20% per 1pp.")

sc = current_scenario()
result = run_stress(lines, supply, sc)
s = result.summary
st.session_state.last_result_summary = s

# ---------------------------------------------------------------- results --------------
st.divider()
st.subheader("Result")
verdict_banner(s)
m = st.columns(5)
m[0].metric("Lowest coverage", fmt_cov(s["min_coverage"]),
            delta=f"{(s['min_coverage'] - s['start_coverage']) * 100:+.2f}pp vs start", delta_color="normal")
m[1].metric("Value per token (worst)", fmt_token(s["min_token_value"]))
m[2].metric("Total losses", fmt_bn(s["total_loss"], 3))
m[3].metric("Redemptions paid", fmt_bn(s["paid"]), help=f"Requested {fmt_bn(s['requested'])}")
m[4].metric("Unmet at end", fmt_bn(s["unmet"]),
            delta=None if s["first_breach_day"] is None else f"late from day {s['first_breach_day']}",
            delta_color="inverse")

for line in narrative(s, sc, supply):
    st.markdown("- " + line)

g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(charts.reserves_vs_tokens(result.daily), width="stretch",
                    config={"displayModeBar": False})
with g2:
    st.plotly_chart(charts.coverage_path(result.daily), width="stretch", config={"displayModeBar": False})
g3, g4 = st.columns(2)
with g3:
    st.plotly_chart(charts.redemptions_bars(result.daily), width="stretch",
                    config={"displayModeBar": False})
with g4:
    st.plotly_chart(charts.loss_breakdown(s), width="stretch", config={"displayModeBar": False})
st.plotly_chart(charts.holdings_used(result.by_holding), width="stretch", config={"displayModeBar": False})

with st.expander("Day-by-day table", icon=":material/table:"):
    show = result.daily.rename(columns={
        "day": "Day", "new_requests": "New requests", "queued_in": "Carried over", "requested": "Requested",
        "paid": "Paid", "unmet": "Unmet", "fire_sale_loss": "Fire-sale loss", "supply": "Tokens",
        "reserves": "Reserves", "liquid_next_day": "Liquid next day", "coverage": "Coverage",
        "panic_multiplier": "Panic x"})
    st.dataframe(show.style.format({c: "{:,.3f}" for c in show.columns if c != "Day"}),
                 width="stretch", hide_index=True)
    st.download_button("Download CSV", result.daily.to_csv(index=False), file_name="pegguard_stress_run.csv",
                       mime="text/csv", icon=":material/download:")
