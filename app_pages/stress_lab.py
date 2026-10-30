"""Stress Lab: the main experience. Pick a stablecoin, pick a crisis, run it, then see the answer and how it was
derived. A second tab maps every rate shock and run size to find where the peg breaks."""

from dataclasses import replace

import pandas as pd
import streamlit as st

from app_pages.common import (WAIT_OPTIONS, apply_scenario, asset_class_labels, basis_badge, basis_notice,
                              current_portfolio, current_scenario, esc, fmt_bn, fmt_bp, fmt_cov, fmt_m, fmt_token,
                              matching_crisis, narrative, on_preset_change, page_header, portfolio_key, position_m,
                              scenario_library_options, section, verdict_banner, verdict_chip, wait_label)
from pegguard import charts
from pegguard.analysis import breaking_point_grid, position_outcome, stress_sensitivity, survival_frontier
from pegguard.charts import BAD, GOOD, WARN
from pegguard.engine import PAR_TOL, Scenario, run_stress
from pegguard.presets import all_presets, preset_names
from pegguard.reserves import composition, frame_to_lines

page_header("Start here", "Stress Lab",
            "Pick a stablecoin, pick a crisis, and see whether every holder still gets $1 on time, what it means "
            "for your position, and exactly how the result was derived.")

CRISIS_NOTES = {
    "Calm": "A normal week: 5% of tokens redeemed over 5 days, no valuation shocks.",
    "Rate shock": "Yields jump 300bp overnight, then 20% of holders redeem over 5 days in a stressed market "
                  "(fire-sale discounts x2).",
    "Crypto crash": "Bitcoin -50%, gold -10%, other investments -30% and a 10% loss on secured loans; 30% of "
                    "holders redeem with fire-sale discounts x3.",
    "Bank failure": "30% of the reserves' bank cash is frozen at a failed bank and assumed lost; 25% of holders "
                    "redeem, half of them on day 1.",
    "Full panic": "+150bp, crypto -40%, a 15% loan loss and a 50% run with panic feedback: redemptions speed up "
                  "as reserves fall below par.",
}


def _short(name: str) -> str:
    return name.split(":")[0]


def _pick_coin() -> None:
    st.session_state.preset_id = st.session_state.lab_coin
    on_preset_change()


def _pick_crisis() -> None:
    pick = st.session_state.lab_crisis
    lib = scenario_library_options()
    if pick in lib:
        apply_scenario(lib[pick])


meta = st.session_state.portfolio_meta

# ---------------------------------------------------------------- step 1: stablecoin ---
lines, supply = current_portfolio()
reserves = sum(l.amount_bn for l in lines)
left, right = st.columns([1.35, 1])
with left:
    section("Choose a stablecoin", "Step 1")
    names = preset_names()
    st.session_state.lab_coin = st.session_state.preset_id  # keep in step with the sidebar
    st.selectbox("Stablecoin or benchmark portfolio", options=list(names), format_func=names.get, key="lab_coin",
                 on_change=_pick_coin)
    st.markdown(f'<div class="pg-note">{basis_badge(meta.get("basis", "hypothetical"))} '
                f'{meta.get("description", "")}</div>'.replace("$", "&#36;"), unsafe_allow_html=True)
    basis_notice(meta)
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

# ---------------------------------------------------------------- step 2: crisis -------
st.divider()
section("Choose a crisis", "Step 2")
lib = scenario_library_options()
st.session_state.lab_crisis = matching_crisis() or "Custom"
st.segmented_control("Crisis", options=list(lib) + ["Custom"], format_func=_short, key="lab_crisis",
                     on_change=_pick_crisis, label_visibility="collapsed")
picked = st.session_state.lab_crisis
st.caption(esc(CRISIS_NOTES.get(_short(picked), "") if picked in lib
               else "Custom: your own settings. Pick a crisis above to start from a standard one."))

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.slider("Interest-rate shock (bp)", -100.0, 500.0, step=25.0, key="sc_rate",
              help="Instant parallel rise in yields. Reprices bills and notes (Week 3 bond maths).")
with c2:
    st.slider("Run size (% of tokens asking to redeem)", 0.0, 100.0, step=5.0, key="sc_run")
with c3:
    st.slider("Run length (business days)", 1, 20, key="sc_days",
              help="How many days new redemption requests keep arriving.")
with c4:
    st.select_slider("Acceptable wait for redemptions", options=list(WAIT_OPTIONS), format_func=wait_label,
                     key="sc_wait",
                     help="How long a holder may wait for their $1 before the request counts as late. Each day's "
                          "requests are checked against this deadline. MAS requires par redemption within 5 "
                          "business days.")

with st.expander("More shocks: bank failure, crypto crash, fire sales, panic", icon=":material/tune:"):
    a1, a2, a3 = st.columns(3)
    with a1:
        st.slider("Bank cash frozen in a bank failure (%)", 0.0, 100.0, step=5.0, key="sc_freeze",
                  help="Share of the reserves' bank deposits stuck at a failed bank (USDC had $3.3bn at SVB).")
        st.slider("Expected recovery on frozen cash (%)", 0.0, 100.0, step=5.0, key="sc_recovery",
                  help="The unrecovered share is a permanent loss.")
        st.select_slider("Frozen cash usable again on", options=list(range(0, 21)),
                         format_func=lambda d: "Never" if d == 0 else f"Day {d}", key="sc_release",
                         help="When the recovered share can be spent again to pay redemptions. 'Never' keeps it "
                              "frozen for the whole run (stuck); the SVB deposits were released after a weekend.")
    with a2:
        st.slider("Bitcoin / crypto price change (%)", -90.0, 0.0, step=5.0, key="sc_crypto")
        st.slider("Gold price change (%)", -50.0, 10.0, step=5.0, key="sc_gold")
        st.slider("Equities / other investments change (%)", -80.0, 10.0, step=5.0, key="sc_risk")
        st.slider("Credit loss on secured loans (%)", 0.0, 100.0, step=5.0, key="sc_loan")
    with a3:
        st.slider("How front-loaded the run is", 0.0, 0.9, step=0.05, key="sc_front",
                  help="0 = spread evenly; 0.5 = each day's requests are half the previous day's.")
        st.slider("Fire-sale stress multiplier", 0.0, 10.0, step=0.5, key="sc_stress",
                  help="Scales every asset's fire-sale discount. 1 = orderly market, 3+ = crisis. The results "
                       "show the same scenario at several levels side by side.")
        st.slider("Panic feedback", 0.0, 1.0, step=0.05, key="sc_panic",
                  help="Extra redemptions for each 1pp that reserves fall below par. 0.2 = +20% per 1pp.")

sc = current_scenario()
result = run_stress(lines, supply, sc)
s = result.summary
st.session_state.last_result_summary = s
pos = position_m()
out = position_outcome(s, result.daily, pos)
deadline = wait_label(s["max_wait_days"])
deadline_txt = "the same-day deadline" if s["max_wait_days"] == 0 else f"the {deadline} deadline"


# ---------------------------------------------------------------- step 3: outcome ------

def _card(num: int, question: str, answer: str, color: str, detail: str) -> str:
    return (f'<div class="pg-q" style="border-top-color:{color}"><div class="n">Question {num}</div>'
            f'<div class="t">{question}</div><div class="a" style="color:{color}">{answer}</div>'
            f'<div class="d">{detail}</div></div>')


def question_cards() -> str:
    # 1. Backing
    if s["min_coverage"] >= PAR_TOL:
        q1 = _card(1, "Is there enough backing?", "Yes", GOOD,
                   f"Reserves never fell below $1 per token. Lowest coverage {fmt_cov(s['min_coverage'])}, a "
                   f"cushion of {fmt_bp(s['min_coverage'] - 1)}.")
    else:
        drivers = {"the rate shock": s["rate_loss"], "price and credit shocks": s["price_loss"],
                   "frozen cash written off": s["frozen_writedown"], "fire-sale discounts": s["fire_sale_loss"]}
        top = max(drivers, key=drivers.get)
        run_effect = (" Paying early redeemers $1 while reserves were short pushed the shortfall onto those who stay."
                      if s["day0_coverage"] < 1 and s["min_coverage"] < s["day0_coverage"] - 0.01 else "")
        q1 = _card(1, "Is there enough backing?", "No", BAD,
                   f"Reserves fell to {fmt_token(s['min_token_value'])} per token "
                   f"({fmt_bp(s['min_coverage'] - 1)} vs par). Losses of {fmt_bn(s['total_loss'])}, mostly "
                   f"{top}.{run_effect}")
    # 2. Timeliness
    if s["requested"] <= 1e-9:
        q2 = _card(2, "Were redemptions paid on time?", "No requests", GOOD, "Nobody redeemed in this scenario.")
    elif s["first_breach_day"] is None:
        q2 = _card(2, "Were redemptions paid on time?", "Yes", GOOD,
                   f"All {fmt_bn(s['paid'])} of requests were paid within {deadline_txt}.")
    else:
        share = s["late_amount"] / s["requested"]
        left_txt = f" {fmt_bn(s['unmet'])} was still unpaid at the end." if s["unmet"] > 1e-6 else ""
        q2 = _card(2, "Were redemptions paid on time?", "No", BAD if share > 0.05 else WARN,
                   f"{fmt_bn(s['late_amount'])} ({share:.0%} of requests) waited past {deadline_txt}, "
                   f"starting on day {s['first_breach_day']}.{left_txt}")
    # 3. Position
    if out["exit_day"] is not None:
        exit_txt = (f"paid in full on day {out['exit_day']}, "
                    + ("within the deadline." if out["exit_on_time"] else f"after {deadline_txt}."))
    else:
        exit_txt = f"only {out['exit_share_paid']:.0%} paid by day {out['last_day']}."
    loss = out["hold_loss"]
    color = BAD if loss > 1e-6 else (GOOD if out["exit_on_time"] else WARN)
    q3 = _card(3, f"What does it mean for your {fmt_m(pos, 1)}?",
               f"-{fmt_m(loss)}" if loss > 1e-6 else "No loss", color,
               f"<b>Hold:</b> worth {fmt_m(out['hold_value'])} at the low point ({out['haircut_bp']:,.0f}bp "
               f"haircut).<br><b>Redeem on day 1:</b> {exit_txt}")
    return '<div class="pg-qs">' + q1 + q2 + q3 + "</div>"


st.divider()
section("Results", "Step 3 · Outcome")
tab_run, tab_bp = st.tabs([":material/insights: Your scenario", ":material/grid_on: Breaking point"])

with tab_run:
    verdict_banner(s)
    st.markdown(question_cards().replace("$", "&#36;"), unsafe_allow_html=True)

    m = st.columns(5)
    m[0].metric("Lowest coverage", fmt_cov(s["min_coverage"]),
                delta=f"{(s['min_coverage'] - s['start_coverage']) * 1e4:+,.0f}bp vs start", delta_color="normal")
    haircut_bp = max(0.0, 1 - s["min_token_value"]) * 1e4
    m[1].metric("Worst token value", fmt_token(s["min_token_value"]),
                delta=f"-{haircut_bp:,.0f}bp" if haircut_bp >= 0.5 else None, delta_color="normal")
    m[2].metric("Total losses", fmt_bn(s["total_loss"], 3),
                help=f"{s['total_loss'] / reserves * 1e4:,.0f}bp of starting reserves" if reserves else None)
    m[3].metric("Paid late", fmt_bn(s["late_amount"]),
                delta=None if s["first_breach_day"] is None else f"from day {s['first_breach_day']}",
                delta_color="inverse",
                help=f"Requests still waiting when their deadline ({deadline}) passed")
    m[4].metric("Unmet at end", fmt_bn(s["unmet"]),
                help=f"Requested {fmt_bn(s['requested'])}, paid {fmt_bn(s['paid'])} by day {s['days_simulated']}")

    # ------------------------------------------------ how the result was derived
    st.write("")
    section("How this result was derived")
    e1, e2 = st.columns([1.15, 1])
    with e1:
        for line in narrative(s, sc, supply):
            st.markdown("- " + line)
    with e2:
        st.plotly_chart(charts.holdings_used(result.by_holding), width="stretch", config={"displayModeBar": False})

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

    # ------------------------------------------------ fire-sale sensitivity
    st.write("")
    section("Same scenario at different fire-sale stress", "Sensitivity")
    st.caption("Each row re-runs your scenario with only the fire-sale stress multiplier changed (1 = orderly "
               "market, 3+ = crisis), so you can compare without moving the slider. Your setting is highlighted.")
    sens = stress_sensitivity(lines, supply, sc)
    html = ['<table class="pg-table"><tr><th>Fire-sale stress</th><th>Verdict</th><th>Worst value / token</th>'
            '<th>Fire-sale losses</th><th>Paid late</th><th>Your loss if you hold</th></tr>']
    for _, r in sens.iterrows():
        cls = ' class="cur"' if r["current"] else ""
        label = f"x{r['stress']:g}" + (" (yours)" if r["current"] else "")
        your_loss = pos * max(0.0, 1 - r["min_token_value"])
        html.append(f'<tr{cls}><td class="name">{label}</td><td>{verdict_chip(r["verdict"])}</td>'
                    f'<td>{fmt_token(r["min_token_value"])}</td><td>{fmt_bn(r["fire_sale_loss"], 3)}</td>'
                    f'<td>{fmt_bn(r["late_amount"])}</td><td>{fmt_m(your_loss)}</td></tr>')
    html.append("</table>")
    st.markdown("".join(html).replace("$", "&#36;"), unsafe_allow_html=True)

    with st.expander("Day-by-day table and export", icon=":material/table:"):
        show = result.daily.rename(columns={
            "day": "Day", "new_requests": "New requests", "queued_in": "Carried over", "requested": "Requested",
            "paid": "Paid", "unmet": "Unmet", "fire_sale_loss": "Fire-sale loss", "supply": "Tokens",
            "reserves": "Reserves", "liquid_next_day": "Liquid next day", "coverage": "Coverage",
            "panic_multiplier": "Panic x"})
        st.dataframe(show.style.format({c: "{:,.3f}" for c in show.columns if c != "Day"}),
                     width="stretch", hide_index=True)
        report = pd.DataFrame([{
            "portfolio": meta["name"], "data_basis": meta.get("basis", ""), **sc.to_dict(),
            **{k: v for k, v in s.items() if k not in ("headline",)},
            "position_m": pos, "position_hold_value_m": out["hold_value"], "position_loss_m": out["hold_loss"],
            "position_haircut_bp": out["haircut_bp"], "position_exit_day": out["exit_day"],
            "position_exit_on_time": out["exit_on_time"], "position_exit_share_paid": out["exit_share_paid"],
        }])
        d1, d2 = st.columns(2)
        d1.download_button("Day-by-day CSV", result.daily.to_csv(index=False), file_name="pegguard_stress_run.csv",
                           mime="text/csv", icon=":material/download:")
        d2.download_button("Scenario summary CSV", report.to_csv(index=False),
                           file_name="pegguard_scenario_summary.csv", mime="text/csv", icon=":material/download:",
                           help="Settings, results and your position in one row, for a risk report")


# ---------------------------------------------------------------- breaking point -------


def _grid_scenario(sc: Scenario) -> dict:
    """Scenario without the two grid axes, so moving those sliders reuses the cached grid."""
    return replace(sc, name="grid", rate_shock_bp=0.0, redemption_pct=0.0).to_dict()


@st.cache_data(show_spinner="Running 441 stress tests...")
def grid_for(pkey: tuple, sc_dict: dict) -> pd.DataFrame:
    df = pd.DataFrame([list(r) for r in pkey[0]],
                      columns=["Holding", "Asset class", "Amount ($bn)", "Maturity (yrs)", "Yield (%)"])
    for col in ["Amount ($bn)", "Maturity (yrs)", "Yield (%)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return breaking_point_grid(frame_to_lines(df), pkey[1], Scenario(**sc_dict))


@st.cache_data(show_spinner=False)
def compare(bp: int, sc_dict: dict) -> pd.DataFrame:
    rows = []
    for p in all_presets():
        base = replace(Scenario(**sc_dict), rate_shock_bp=float(bp))
        g = breaking_point_grid(p.lines, p.supply_bn, base, rate_shocks_bp=[bp], run_sizes_pct=range(0, 105, 5))
        fr = survival_frontier(g)
        v = fr["max_run_holds"].iloc[0]
        rows.append({"Portfolio": p.name, "Largest run survived (%)": 0.0 if pd.isna(v) else v})
    return pd.DataFrame(rows).sort_values("Largest run survived (%)", ascending=False)


with tab_bp:
    st.caption(f"Every cell is a full stress run using your scenario above, with only the rate shock and run size "
               f"changed. Red means reserves fell below $1 per token; \"late\" means some redemptions missed the "
               f"deadline ({deadline}). The dashed line is the largest run paid on time; the solid line is the "
               f"largest run that is paid on time *and* leaves reserves at par. The marker is your current scenario."
               .replace("$", "\\$"))
    grid = grid_for(portfolio_key(), _grid_scenario(sc))
    frontier = survival_frontier(grid)
    st.plotly_chart(charts.breaking_heatmap(grid, frontier, marker=(sc.rate_shock_bp, sc.redemption_pct)),
                    width="stretch", config={"displayModeBar": False})

    b1, b2 = st.columns([1, 1.2])
    with b1:
        section("Survival frontier")
        f = frontier.rename(columns={"rate_shock_bp": "Shock (bp)",
                                     "max_run_paid_on_time": "Paid on time",
                                     "max_run_at_par": "At par",
                                     "max_run_holds": "Fully holds"})
        f = f.iloc[::2].copy()
        for col in ["Paid on time", "At par", "Fully holds"]:
            f[col] = f[col].map(lambda v: "never" if pd.isna(v) else f"{v:.0f}%")
        f["Shock (bp)"] = f["Shock (bp)"].map(lambda v: f"+{v:.0f}")
        st.dataframe(f, width="stretch", hide_index=True, height=420)
        st.caption("Largest run (% of tokens) that is paid on time / leaves reserves at par / does both. "
                   "'never' means reserves are already below par at that rate shock before anyone redeems.")
    with b2:
        section("Compare portfolios")
        bp_pick = st.select_slider("Rate shock for the comparison (bp)", options=list(range(0, 525, 25)),
                                   value=int(min(max(sc.rate_shock_bp, 0), 500) // 25 * 25), key="bp_compare")
        cmp = compare(bp_pick, _grid_scenario(sc))
        st.plotly_chart(charts.preset_frontier_bars(cmp), width="stretch", config={"displayModeBar": False})
        st.caption("Uses each portfolio's bundled reserves (not your edits) and your other scenario settings. "
                   "Benchmarks marked hypothetical or reconstructed are teaching portfolios, not real reserves.")

st.divider()
st.page_link("app_pages/overview.py", label="Next: compare every coin on the summary Dashboard",
             icon=":material/arrow_forward:")
