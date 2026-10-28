"""Case study: USDC and the Silicon Valley Bank weekend (10-13 March 2023)."""

import streamlit as st

from app_pages.common import apply_scenario, esc, fmt_bn, request_preset
from pegguard import charts
from pegguard.data_sources import load_svb_episode
from pegguard.engine import Scenario, run_stress
from pegguard.presets import load_preset

st.markdown('<div class="pg-hero">Case: USDC and the SVB weekend</div>', unsafe_allow_html=True)
st.markdown('<div class="pg-sub">On Friday 10 March 2023, Circle said $3.3bn of roughly $40bn of USDC reserves was '
            'stuck at Silicon Valley Bank. Over the weekend USDC traded as low as about $0.87. Can the model explain '
            'that price?</div>', unsafe_allow_html=True)

p = load_preset("usdc_2023_svb")
svb_cash = sum(l.amount_bn for l in p.lines if "Silicon Valley" in l.name)
bank_cash = sum(l.amount_bn for l in p.lines if l.asset_class == "cash_bank")
freeze_pct = svb_cash / bank_cash * 100

recovery = st.slider("Assumed recovery on the $3.3bn at SVB (%)", 0, 100, 0, step=5, key="svb_recovery")


def nav(rec: float) -> float:
    sc = Scenario(redemption_pct=0, bank_freeze_pct=freeze_pct, frozen_recovery_pct=rec)
    return run_stress(p.lines, p.supply_bn, sc).summary["day0_coverage"]


nav_worst, nav_chosen = nav(0), nav(recovery)
prices, meta = load_svb_episode()
low = float(prices["price"].min())

k = st.columns(4)
k[0].metric("Reserves at SVB", fmt_bn(svb_cash, 1), help=f"{svb_cash / p.supply_bn:.1%} of tokens")
k[1].metric("Value/token if SVB cash lost", f"${nav_worst:.3f}", help="Model: day-0 reserves per token with 0% recovery")
k[2].metric("Value/token at your recovery", f"${nav_chosen:.3f}", help=f"Model with {recovery}% recovery on SVB deposits")
k[3].metric("Market low", f"${low:.3f}", delta=f"{(low - nav_worst) * 100:+.1f}c vs worst case", delta_color="off")

st.plotly_chart(charts.svb_episode(prices, nav_worst, nav_chosen, recovery), width="stretch",
                config={"displayModeBar": False})
st.caption(esc(meta["note"]))

st.subheader("What the model says")
st.markdown(esc(f"""
- **Even if every dollar at SVB were lost, USDC was still worth about ${nav_worst:.3f}.** The other ~92% of reserves
  sat in cash at other banks and a government money market fund, which a rate or bank shock barely touches.
- **The market went lower than that worst case (about ${low:.2f}).** The gap is not a solvency problem but an
  **access** problem: SVB failed on a Friday and US bank rails were shut for the weekend, so nobody could redeem USDC for
  dollars until Monday. Without the arbitrage of redeeming at $1, panic set the price.
- **Recovery came from outside the issuer.** On Sunday evening US authorities guaranteed all SVB deposits. That moves
  the model to 100% recovery (value $1.000) and the market price followed within hours.
- **Lesson for a treasury team:** watch *where* the bank cash sits and *when* you can redeem, not only how much backing
  there is. This is the Week 9-10 point that stablecoins carry bank-run risk (Diamond & Dybvig 1983), and why
  regulators now demand diversified, short-dated reserves and fast par redemption.
"""))

if st.button("Re-run this in the Stress Lab", type="primary", icon=":material/science:"):
    request_preset("usdc_2023_svb")
    apply_scenario(Scenario(rate_shock_bp=0, redemption_pct=20, horizon_days=3, front_load=0.5,
                            bank_freeze_pct=round(freeze_pct, 1), frozen_recovery_pct=float(recovery),
                            stress_multiplier=2))
    st.switch_page("app_pages/stress_lab.py")
