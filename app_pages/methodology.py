"""Methodology: how the model works, every assumption, and its limits."""

import pandas as pd
import streamlit as st

from app_pages.common import page_header, section
from pegguard.reserves import ASSET_CLASSES

page_header("How it works", "Methodology",
            "A transparent, deliberately simple model. Every number below can be changed, and every result "
            "can be reproduced from the command line.")

section("Day 0: shocks", "01")
st.markdown(r"""
**Interest rates (Week 3 bond maths).** A parallel shock $\Delta y$ reprices every rate-sensitive holding instantly.

* Bills (maturity $\le$ 1 year) are zero-coupon: $\;P = \dfrac{1}{(1+y)^T}$, so the value factor is $\dfrac{(1+y)^T}{(1+y+\Delta y)^T}$.
* Notes are coupon bonds bought at par (coupon = yield): $\;P=\sum_{i=1}^{n}\dfrac{c/k}{(1+y/k)^i}+\dfrac{1}{(1+y/k)^n}$, repriced at $y+\Delta y$.
* Government money market funds keep a stable \$1.00 NAV unless the shadow NAV falls below \$0.995 ("breaking the buck").

**Other shocks.** Gold, crypto and other investments fall by the chosen %. Secured loans take a credit loss. A bank
failure freezes a share of the bank cash; the frozen amount is valued at the assumed recovery rate and cannot be used
to pay redemptions during the run.
""")

section("Days 1 to N: the run", "02")
st.markdown(r"""
Base redemption requests follow a front-loaded schedule: day $d$ gets weight $\propto (1-f)^{d-1}$, scaled so the run
adds up to the chosen % of tokens. Requests not paid on a day are carried over.

The issuer pays **\$1 per token** by raising cash through a **liquidity waterfall**, cheapest and fastest first:
cash, repo, money market fund, T-bills (shortest first), notes, gold, crypto, other investments, loans.
Each holding can sell at most *daily liquidity × its post-shock value* per day, and every dollar raised from a sale costs
a fire-sale discount: $\;\text{proceeds} = \text{sold} \times (1 - \text{discount} \times \text{stress multiplier})$.

**Panic feedback (Diamond & Dybvig 1983).** Optional. When coverage falls below 1, each day's new requests are
multiplied by $1 + k \times 100 \times (1 - \text{coverage})$. Because early redeemers are paid in full while
reserves are short, the shortfall concentrates on the holders who stay. That first-mover advantage is what makes runs
self-fulfilling.
""")

section("Outputs", "03")
st.markdown(r"""
* **Coverage** = reserves (marked to market, frozen cash at recovery value) ÷ tokens outstanding, every day.
* **Value per token** = min(1, coverage): what a token is worth if the issuer were wound down at that point.
* **Verdict:** **HOLDS** (paid on time, coverage ≥ 1) · **LIQUIDITY STRAIN** (solvent, but some redemptions are late)
  · **BELOW PAR** (paid, but coverage < 1) · **BREAKS** (both).
* **Breaking point** (a Stress Lab tab) re-runs the engine on a 21 × 21 grid of rate shocks (0-500bp) and run sizes (0-100%).
""")

section("Asset-class assumptions", "04")
df = pd.DataFrame([
    {"Asset class": a.label, "Daily liquidity": a.daily_liquidity, "Fire-sale discount (bp)": a.fire_sale_bps,
     "Rate-sensitive": a.rate_kind != "none", "GENIUS-eligible": a.genius, "MAS-eligible": a.mas,
     "Waterfall order": a.rank, "Why": a.note}
    for a in ASSET_CLASSES.values()
])
st.dataframe(df.style.format({"Daily liquidity": "{:.0%}", "Fire-sale discount (bp)": "{:.0f}"}), width="stretch",
             hide_index=True)
st.caption("Defaults are judgement calls, set conservatively and documented in pegguard/reserves.py. The stress "
           "multiplier scales all discounts together, which is the main sensitivity to test.")

section("What the model leaves out (on purpose)", "05")
st.markdown("""
* **No secondary-market price model.** We value what reserves can pay, not where the token trades. USDC's March 2023
  depeg during the SVB weekend shows the two can differ when redemption is closed.
* **No interest income, fees or issuer capital injections** during the run (all small over days, or discretionary).
* **One parallel rate shock**, no yield-curve twists; no correlation model between shocks. Users choose the combination.
* **Reserve data** come from issuer reports (quarterly / monthly), so they are point-in-time. Presets show the as-of date.
""")

section("Sources", "06")
st.markdown("""
* Circle Internet Group, Form 10-Q for the quarter ended 30 June 2026 (SEC EDGAR): USDC reserves and Circle Reserve Fund.
* Tether Q2 2026 reserves report (BDO Italia attestation, 30 June 2026), via stablecoininsider.org summary.
* CNBC (11 Mar 2023): *Stablecoin USDC breaks dollar peg after firm reveals it has $3.3 billion in SVB exposure.*
* Paxos, *The GENIUS Act* (2026 summary of the July 2025 law): permitted reserve assets and 93-day bill limit.
* Reed Smith (Aug 2023): *Singapore stablecoin regulation: MAS confirms its framework* (100% backing, 5-business-day
  par redemption, monthly attestation).
* Diamond, D. & Dybvig, P. (1983). Bank runs, deposit insurance, and liquidity. *Journal of Political Economy* 91(3).
* Live data: DefiLlama stablecoin and coin-price APIs (free, no key).
""")
