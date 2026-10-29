# Q&A preparation

20% of the grade is presentation clarity and Q&A defence. These are the questions most likely to come up, with
short answers every team member should be able to give.

## Architecture and technical choices

**Why Streamlit and Python instead of a web framework or smart contracts?**
The value is in the calculation, not the UI. Python lets us test the engine directly (19 pytest tests), and Streamlit
gives a working interface fast. The engine (`pegguard/`) has no UI code, so it could sit behind an API later.

**Why a deterministic scenario model, not Monte Carlo or machine learning?**
Risk committees need to audit and explain the number. With a deterministic model every input maps to an output you can
trace by hand. ML would need historical depeg data, and there are only a handful of real events. The breaking-point
grid gives us the sensitivity analysis that a simulation would.

**How do you reprice bonds after a rate shock?**
Week 3 bond maths. Bills (1 year or less) are priced as zero-coupon bonds: P = 1/(1+y)^T. Notes are coupon bonds bought
at par (coupon = yield), so the price after a shock is the PV of the same coupons at y + Δy. The unit tests check this against
hand calculations (e.g. a 10-year 7% annual-coupon bond at a 5% yield = $1,154.43).

**Why does a money market fund not lose value on a rate shock?**
Government MMFs keep a stable $1.00 NAV unless the shadow NAV drops below $0.995 ("breaking the buck"). With about a
30-day weighted maturity, even +300bp is only about -0.25%, so the NAV holds. We model that rule explicitly.

**Where do the liquidity and fire-sale numbers come from?**
They are transparent judgement calls, ordered by how liquid each market really is (cash and overnight repo instant;
T-bills deep but not infinite; loans almost locked up). They are shown on the Methodology page, editable per line, and
the stress multiplier scales all of them together. The breaking-point map in the Stress Lab shows how much conclusions move.

**What is the liquidity waterfall and why that order?**
Cheapest and fastest first: cash, repo, MMF, bills (shortest first), notes, gold, crypto, other, loans. That is what a
rational issuer does: it minimises fire-sale losses. A different order would only make results worse.

**How do you model panic?**
Optional feedback inspired by Diamond & Dybvig (1983): each day's new requests are multiplied by
1 + k × 100 × (1 − coverage). When reserves are below par, paying early redeemers $1 leaves less for the rest, so
staying is irrational. Off by default, so base results are not driven by it.

**What happens if the API is down during the demo?**
Nothing. Everything except the Live Monitor section on the Dashboard works offline, and that section falls back to the last cached fetch, then to the
bundled snapshot. We demo with live data off.

## Data and validity

**How accurate are the USDT and USDC presets?**
Category amounts come from the Q2 2026 reports: Circle's 10-Q and Tether's BDO attestation (via a secondary
summary). Maturities and yields are labelled assumptions. The as-of date and source are shown in the app. Anyone can
update `data/presets.json` or edit in the UI.

**Did you validate the model?**
Against the one clean real-world event: USDC in March 2023. The model says worst-case value was about $0.918 (if all SVB
cash were lost). The market low was about $0.87-0.88. The gap is explained by redemption being closed over the weekend,
which the model does not price, and we say so.

**USDT shows "BELOW PAR" in a crypto crash. Are you saying Tether is insolvent?**
No. We say that under that specific combined shock (BTC -50%, gold -10%, other investments -30%, 10% loan losses, 30%
run), the marked-to-market reserves would fall below tokens outstanding. Tether's 2% buffer absorbs smaller shocks. It
is a scenario, not a forecast.

**Why is the 'USDC on 10 Mar 2023' preset so sensitive?**
It has exactly 100% backing, so there is no buffer: even small fire-sale discounts push it below par. That is a real
design lesson: a capital buffer above 100% buys resilience.

## Business

**Who exactly pays?**
Treasury teams at payment institutions and fintechs holding stablecoin float, and risk teams at exchanges and
custodians setting collateral haircuts. Subscription US$500-1,500/month; data licence US$25-100k/year.

**Why wouldn't they just read the attestation?**
An attestation shows composition at one date. It does not say whether the reserves can pay a 30% run in five days
after a 300bp shock. That translation is the product.

**Isn't this what rating agencies do?**
Rating agencies give a qualitative score. We give an interactive, assumption-level stress test the client can run on
their own scenarios and show their risk committee.

**What's the biggest risk to the business?**
Data freshness (issuers publish monthly/quarterly) and conflicts of interest if issuers pay for results. We would keep
the methodology public and not take issuer fees for scores.

## Course links (in case you're asked "how does this relate to the module?")

* Week 3: bond pricing, YTM, duration, price-yield inverse relationship.
* Week 5: systematic vs idiosyncratic risk (bank concentration is idiosyncratic and diversifiable; rate shocks are systematic).
* Week 9: Diamond & Dybvig runs, the "three questions" (function: payments/deposits; cost that falls: verification; who keeps the value).
* Week 10: fiat-backed vs crypto-backed stablecoins, "what if bond prices fall / what if there is a run", GENIUS Act, MAS.
