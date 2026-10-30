"""Issuer Profile: data freshness, interest-rate risk, liquidity ladder and a simplified GENIUS Act / MAS check."""

from datetime import date

import pandas as pd
import streamlit as st

from app_pages.common import basis_notice, current_portfolio, fmt_bn, fmt_bp, page_header, section
from pegguard import charts
from pegguard.analysis import regulatory_check, risk_profile
from pegguard.pricing import modified_duration

page_header("Due diligence", "Issuer Profile",
            "Four questions to ask before holding a stablecoin: how fresh is the reserve data, how rate-sensitive "
            "are the reserves, how fast can they become cash, and are they the assets regulators allow?")

STALE_DAYS = 92  # older than about one quarter of attestations


def data_age(as_of: str, edited: bool) -> tuple[str, str | None]:
    """Days since the reserve snapshot, with a warning when it is older than a quarter."""
    if edited:
        return "Edited", None
    try:
        days = (date.today() - date.fromisoformat(as_of)).days
    except ValueError:
        return "n/a", None  # hypothetical portfolios have no report date
    return f"{days:,} days", ("stale" if days > STALE_DAYS else None)

lines, supply = current_portfolio()
reserves = sum(l.amount_bn for l in lines)
rp = risk_profile(lines, supply)
rc = regulatory_check(lines, supply)

meta = st.session_state.portfolio_meta
basis_notice(meta)
age, stale = data_age(meta.get("as_of", ""), meta.get("edited", False))
k = st.columns(5)
k[0].metric("Reserve data age", age, delta=stale, delta_color="inverse" if stale else "off",
            help=f"Days since the reserve report this portfolio is built from (as of {meta.get('as_of', '')}). "
                 "Check for a newer attestation before relying on the numbers.")
k[1].metric("Buffer above par", fmt_bp(reserves / supply - 1) if supply else "n/a",
            help=f"Reserves minus tokens = {fmt_bn(reserves - supply, 2)}: the loss the issuer can absorb before "
                 "the peg is at risk")
k[2].metric("Loss per +100bp", f"{rp['loss_per_100bp_pct'] * 100:,.0f}bp",
            help=f"About {fmt_bn(rp['dv01_bn'] * 100, 3)} of reserve value lost if all yields rise 1 percentage point")
k[3].metric("Modified duration", f"{rp['duration']:.2f} yrs",
            help=f"Weighted average maturity of rate-sensitive assets: {rp['wam_days']:,.0f} days")
k[4].metric("Cash in 5 days", f"{rp['day5_capacity_share']:.0%}",
            help="Share of tokens that could be paid within 5 business days (the MAS redemption window)")

st.divider()
c1, c2 = st.columns([1.1, 1])
with c1:
    st.plotly_chart(charts.liquidity_ladder(rp["ladder"]), width="stretch", config={"displayModeBar": False})
    st.caption("Assumes orderly markets (no shocks, stress x1). The MAS framework requires par redemption within "
               "5 business days of a request.")
with c2:
    section("Rate risk by holding")
    rows = []
    for l in lines:
        kind = l.spec.rate_kind
        d = 0.0 if kind == "none" else modified_duration("zero" if kind in ("zero", "mmf") else "coupon",
                                                         l.maturity_years, l.yield_pct / 100)
        rows.append({"Holding": l.name, "$bn": l.amount_bn, "Duration": d, "Loss at +100bp ($bn)": l.amount_bn * d / 100})
    st.dataframe(pd.DataFrame(rows).style.format({"$bn": "{:,.2f}", "Duration": "{:.2f}",
                                                  "Loss at +100bp ($bn)": "{:,.3f}"}),
                 width="stretch", hide_index=True)

st.divider()
section("Reserve eligibility (simplified)", "Regulation")
r1, r2 = st.columns(2)
regimes = {
    "GENIUS": ("US GENIUS Act (2025)", "Cash, insured deposits, T-bills of 93 days or less, repo of 7 days or less "
                                       "on bills, government money market funds. 1:1 backing, monthly attestation."),
    "MAS": ("MAS single-currency stablecoin framework (2023)", "Very-low-risk assets: cash, cash equivalents and "
                                                              "short-dated (3 months or less) government debt. At "
                                                              "least 100% backing, par redemption within 5 business "
                                                              "days, monthly attestation."),
}
for col, key in zip((r1, r2), ("GENIUS", "MAS")):
    title, rule = regimes[key]
    res = rc[key]
    with col:
        ok = res["passes"]
        st.markdown(f"**{title}**")
        st.caption(rule)
        st.metric("Eligible reserves / tokens", f"{res['eligible_backing']:.1%}")
        if ok:
            st.markdown(':green[**Passes:** eligible assets cover every token.]')
        else:
            short = fmt_bn((1 - res["eligible_backing"]) * supply).replace("$", "\\$")
            st.markdown(f':red[**Fails:** eligible assets are short by {short}.]')
        det = res["detail"].copy()
        det["Eligible"] = det["Eligible"].map({True: "Yes", False: "No"})
        det = det.rename(columns={"Amount ($bn)": "$bn"})
        with st.expander("Holding-by-holding detail", icon=":material/list:"):
            st.dataframe(det.style.format({"$bn": "{:,.2f}"})
                         .map(lambda v: "color:#15803D; font-weight:600" if v == "Yes"
                              else ("color:#B91C1C; font-weight:600" if v == "No" else ""), subset=["Eligible"]),
                         width="stretch", hide_index=True,
                         column_config={"Holding": st.column_config.TextColumn(width="medium"),
                                        "$bn": st.column_config.NumberColumn(width="small"),
                                        "Eligible": st.column_config.TextColumn(width="small"),
                                        "Reason": st.column_config.TextColumn(width="medium")})
st.caption("Educational simplification of the rules, not legal advice. Check the statute / MAS notice for details.")
