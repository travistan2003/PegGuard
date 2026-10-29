# PegGuard: 8-minute presentation and demo script

Total: 8:00 hard stop. Q&A follows immediately. Suggested split for 4 speakers (A, B, C, D).

## Before you present (checklist)

- [ ] The night before, while online: `python scripts/refresh_snapshot.py` (fills the Live Monitor on the Dashboard with current data).
- [ ] On the demo laptop: `streamlit run app.py`, open http://localhost:8501, **sidebar toggle "Fetch live market data" OFF** (offline demo mode).
- [ ] Browser zoom 110-125% so the back row can read it. Close other tabs and notifications.
- [ ] Keep a screen recording of this exact flow on the desktop as a backup.
- [ ] Rehearse with a timer at least three times. Each click below has been tested.

---

## 0:00-1:30 · Problem and user (Speaker A)

> "Mei runs treasury at a Singapore payment institution. To pay suppliers in Indonesia and the Philippines 24/7, her
> firm keeps 30 million dollars of USDC and USDT as float. Her risk committee asks one question: if things go wrong,
> will these coins still be worth a dollar, and how much should we hold?
>
> Today she has a monthly PDF attestation, a snapshot of what the reserves *were*. In March 2023 USDC fell to 88 cents
> in one weekend because 3.3 billion of its reserves sat at Silicon Valley Bank. A backing ratio of 100% told you
> nothing about that.
>
> So we built PegGuard: a stress tester that asks what happens to a stablecoin's reserves during a run."

## 1:30-6:00 · Live demo (Speaker B drives, Speaker C narrates)

**1. Dashboard (45s).** Point at the USDT and USDC tiles.
> "Mei's firm holds 30 million dollars, set here in the sidebar. Each tile shows the coin's buffer above par, how much
> can be paid out in a day, the largest run it survives, and what Mei's position is worth in the worst standard
> scenario."

Scroll past the **Live Monitor** to the **Scorecard**.
> "Five portfolios, five identical scenarios. Green holds, orange means reserves fell below a dollar per token, red
> means it breaks. Notice every coin fails *differently*. That's the point."

**2. Stress Lab with the SVB-style portfolio (90s).** Sidebar: pick **SVB-style duration mismatch**.
> "This portfolio is 100% backed today, but 60% sits in 10-year notes bought at 1.8%."

Drag **Interest-rate shock to 300bp**, **Run size to 20%**.
> "Day 0: Week 3 bond maths. A 300bp rise knocks about 6 billion off the notes. Then 20% of holders redeem over five
> days. The issuer pays them $1 each by selling through a waterfall: cash first, then bills, then notes at a fire-sale
> discount."

Point at the **Your position** panel and the coverage chart (the plain-English narrative is under **Explain this
result**).
> "Everyone who redeems gets a dollar, but the people who stay are now backed by 81 cents. That's the first-mover
> advantage that makes runs self-fulfilling: Diamond and Dybvig from Week 9."

Open **More shocks**, set **Panic feedback 0.3**.
> "Turn on panic: as coverage falls, redemptions accelerate. Now it breaks."

**3. Breaking point (90s).** Still in the Stress Lab, click the **Breaking point** tab under the scenario.
> "Every cell here is a full stress run, 441 of them. The black line is the largest run this portfolio survives at
> each rate shock. On the right, the same comparison across all portfolios at 200bp: the USDC-style reserves survive any
> run; the SVB-style one survives none."

**4. USDT and liquidity (45s).** Sidebar: pick **USDT-style reserves (Q2 2026)**, go to **Issuer Profile**.
> "USDT is over-collateralised and barely cares about rates. Its weakness is speed: with secured loans and gold, only
> about half of tokens can be paid in one day, and GENIUS-eligible assets cover about 77% of tokens."

## 6:00-7:30 · Scope, trade-offs, next steps (Speaker D)

> "What we deliberately did *not* build: a token price model, user accounts, alerts, yield-curve twists. We chose one
> transparent, deterministic engine because a risk committee has to audit every assumption, and every assumption is
> on the Methodology page and editable.
>
> Next: ingest attestations automatically, alert when a new report moves a coin's breaking point, and sell it as a
> subscription to payment institutions and exchanges setting stablecoin limits."

## 7:30-8:00 · Close (Speaker A)

> "A backing ratio tells you how much is in the vault. PegGuard tells you whether it gets out in time. Thank you."
