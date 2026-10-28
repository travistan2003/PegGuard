"""Live Monitor: current USD stablecoin supply and how closely each coin trades to $1."""

import pandas as pd
import streamlit as st

from app_pages.common import esc
from pegguard import charts
from pegguard.data_sources import load_price_history, load_stablecoins

st.markdown('<div class="pg-hero">Live Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="pg-sub">Supply and peg deviation for the largest USD stablecoins. Supply falling fast while '
            'the price slips below $1 is what an early-stage run looks like from the outside.</div>',
            unsafe_allow_html=True)

live = bool(st.session_state.get("live_data", False))


@st.cache_data(ttl=600, show_spinner="Fetching stablecoin data...")
def get_table(live: bool):
    return load_stablecoins(live=live)


@st.cache_data(ttl=600, show_spinner="Fetching price history...")
def get_history(live: bool):
    return load_price_history(days=90, live=live)


df, meta = get_table(live)
mode_text = {"live": "Live data", "cache": "Cached data", "snapshot": "Bundled snapshot"}.get(meta["mode"], "")
(st.success if meta["mode"] == "live" else st.info)(
    esc(f"**{mode_text}** · as of {meta['as_of']} · {meta['note']}"), icon=":material/database:")
if not live:
    st.caption("Turn on **Fetch live market data** in the sidebar to pull the latest figures from DefiLlama.")

if df.empty:
    st.warning("No stablecoin data available.")
    st.stop()

for c in ["supply_usd", "prev_day_usd", "prev_week_usd", "prev_month_usd", "price", "peg_gap_bps", "chg_7d_pct",
          "chg_30d_pct"]:
    if c in df:
        df[c] = pd.to_numeric(df[c], errors="coerce")
total = df["supply_usd"].sum()
k = st.columns(4)
k[0].metric("USD stablecoins tracked", f"{len(df)}")
k[1].metric("Total supply", f"${total / 1e9:,.1f}bn")
top2 = df.head(2)["supply_usd"].sum() / total if total else float("nan")
k[2].metric("Share of top 2", f"{top2:.0%}" if len(df) > 2 else "n/a",
            help="Concentration: how much of the market two issuers control")
off_peg = df[df["peg_gap_bps"].abs() > 50] if "peg_gap_bps" in df else pd.DataFrame()
k[3].metric("Coins >50bp off peg", f"{len(off_peg)}" if df["price"].notna().any() else "n/a")

c1, c2 = st.columns([1, 1.25])
with c1:
    st.plotly_chart(charts.supply_bars(df), width="stretch", config={"displayModeBar": False})
with c2:
    show = df.head(20)[["symbol", "name", "mechanism", "supply_usd", "chg_7d_pct", "chg_30d_pct", "price",
                        "peg_gap_bps"]].copy()
    show["supply_usd"] = show["supply_usd"] / 1e9
    show = show.rename(columns={"symbol": "Coin", "name": "Name", "mechanism": "Backing", "supply_usd": "Supply ($bn)",
                                "chg_7d_pct": "7d chg (%)", "chg_30d_pct": "30d chg (%)", "price": "Price",
                                "peg_gap_bps": "Peg gap (bp)"})

    def flag(v):
        if pd.isna(v):
            return ""
        return "color:#B91C1C; font-weight:600" if abs(v) > 50 else ("color:#B45309" if abs(v) > 10 else "")

    st.dataframe(show.style.format({"Supply ($bn)": "{:,.2f}", "7d chg (%)": "{:+.1f}", "30d chg (%)": "{:+.1f}",
                                    "Price": "{:.4f}", "Peg gap (bp)": "{:+.0f}"}, na_rep="-")
                 .map(flag, subset=["Peg gap (bp)"]),
                 width="stretch", hide_index=True, height=min(420, 35 * (len(show) + 1) + 3))

hist, hmeta = get_history(live)
if hist.empty:
    st.info(hmeta["note"], icon=":material/cloud_off:")
else:
    coins = sorted(hist["coin"].unique())
    pick = st.multiselect("Coins", coins, default=[c for c in ["USDT", "USDC", "DAI"] if c in coins] or coins[:3])
    st.plotly_chart(charts.peg_history(hist[hist["coin"].isin(pick)]), width="stretch",
                    config={"displayModeBar": False})
    st.caption(f"{hmeta['note']} · as of {hmeta['as_of']}")
