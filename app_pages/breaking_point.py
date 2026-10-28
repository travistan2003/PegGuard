"""Breaking Point: map the whole space of rate shocks x run sizes and find where the peg fails."""

from dataclasses import replace

import pandas as pd
import streamlit as st

from app_pages.common import current_portfolio, current_scenario, portfolio_key
from pegguard import charts
from pegguard.analysis import breaking_point_grid, survival_frontier
from pegguard.engine import Scenario
from pegguard.presets import all_presets
from pegguard.reserves import frame_to_lines

st.markdown('<div class="pg-hero">Breaking Point</div>', unsafe_allow_html=True)
st.markdown('<div class="pg-sub">Every cell is a full stress run. Red means reserves fell below $1 per token; '
            '"late" means some redemptions could not be paid on time. The dashed line is the largest run paid on time; '
            'the solid line is the largest run that is paid on time <i>and</i> leaves reserves at par.</div>', unsafe_allow_html=True)

sc = current_scenario()
st.info(f"Other settings come from the Stress Lab: run over {sc.horizon_days} days, bank freeze "
        f"{sc.bank_freeze_pct:.0f}%, fire-sale stress x{sc.stress_multiplier:.1f}, crypto {sc.crypto_shock_pct:+.0f}%, "
        f"panic {sc.panic_sensitivity:.2f}.", icon=":material/info:")


@st.cache_data(show_spinner="Running 441 stress tests...")
def grid_for(pkey: tuple, sc_dict: dict) -> pd.DataFrame:
    df = pd.DataFrame([list(r) for r in pkey[0]],
                      columns=["Holding", "Asset class", "Amount ($bn)", "Maturity (yrs)", "Yield (%)"])
    for col in ["Amount ($bn)", "Maturity (yrs)", "Yield (%)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return breaking_point_grid(frame_to_lines(df), pkey[1], Scenario(**sc_dict))


lines, supply = current_portfolio()
grid = grid_for(portfolio_key(), sc.to_dict())
frontier = survival_frontier(grid)
st.plotly_chart(charts.breaking_heatmap(grid, frontier, marker=(sc.rate_shock_bp, sc.redemption_pct)),
                width="stretch", config={"displayModeBar": False})

c1, c2 = st.columns([1, 1.2])
with c1:
    st.subheader("Survival frontier")
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

with c2:
    st.subheader("Compare portfolios")
    bp = st.select_slider("Rate shock for the comparison (bp)", options=list(range(0, 525, 25)),
                          value=int(min(max(sc.rate_shock_bp, 0), 500) // 25 * 25), key="bp_compare")

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

    cmp = compare(bp, sc.to_dict())
    st.plotly_chart(charts.preset_frontier_bars(cmp), width="stretch", config={"displayModeBar": False})
    st.caption("Uses each portfolio's bundled reserves (not your edits) and your other Stress Lab settings.")
