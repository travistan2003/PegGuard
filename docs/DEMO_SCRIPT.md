# PegGuard: 8-minute presentation and demo script

Total: 8:00 hard stop. Q&A follows immediately. Suggested split for 4 speakers (A, B, C, D).

## Before you present (checklist)

- [ ] The night before, while online: `python scripts/refresh_snapshot.py` (fills the Live Monitor on the Dashboard with current data).
- [ ] The app opens on the Stress Lab. Check the acceptable wait is on **Same day** before you start.
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

The app opens on the **Stress Lab**. The flow is: choose a coin, choose a crisis, read the answer and how it was
derived, then zoom out to the Dashboard.

**1. Choose a stablecoin (20s).** Step 1: pick **USDT-style reserves (Q2 2026)**. Point at the **Reported** badge.
> "This is Tether's reported reserve mix from its Q2 2026 attestation. Mostly T-bills and repo, but about a quarter in
> gold, bitcoin and secured loans. Mei holds 30 million dollars of it, set in the sidebar."

**2. Choose a crisis (30s).** Step 2: click **Full panic**. Leave the acceptable wait on **Same day**.
> "Rates up 150bp, crypto down 40%, and half of all holders try to leave within a week. As reserves fall below a
> dollar, redemptions speed up: Diamond and Dybvig from Week 9."

**3. The answer as three questions (60s).** Step 3, **Your scenario**. Read the three cards left to right.
> "Is there enough backing? No: reserves fall to about 65 cents per token. Were redemptions paid on time? No: about
> 35 billion dollars of requests miss a same-day deadline. And for Mei's 30 million? Holding loses about 10.5 million.
> Redeeming on day 1 gets her a dollar, but only on day 2."

**4. How it was derived (40s).** Scroll to **How this result was derived**.
> "Day 0, the shocks. Then the run: the issuer pays a dollar per token by selling cash first, then bills, then gold
> and crypto at fire-sale prices. The chart shows what each holding did. Every number here can be traced."

**5. Change the rules, compare side by side (50s).** Step 2: set **Acceptable wait** to **T+5 (MAS)**.
> "Now give the issuer the 5 business days MAS allows. Late payments fall to about 19 billion, but look at backing:
> paying the queue a dollar each from short reserves pushes the loss onto those who stay. It's now 53 cents."

Scroll to **Sensitivity**.
> "And we don't have to remember the last result: the same scenario at fire-sale stress x1, x2, x3 and x5, side by side."

**6. Breaking point (40s).** Click the **Breaking point** tab.
> "Every cell is a full stress run, 441 of them. The line is the largest run the reserves survive at each rate shock.
> On the right, every portfolio at the same shock."

**7. Then the summary (40s).** Click **Next: compare every coin on the summary Dashboard**.
> "Only now do we zoom out: one tile per coin, the live market, and a sortable risk ranking. The scorecard of five
> crises is folded away underneath. Benchmarks are labelled Hypothetical or Reconstructed: they're teaching
> portfolios, not a record of what any coin actually held."

Optional, if time: open **More shocks**, set bank cash frozen 30%, recovery 100% and **Frozen cash usable again on**
Day 2 vs Never, to show stuck cash versus lost money.

## 6:00-7:30 · Scope, trade-offs, next steps (Speaker D)

> "What we deliberately did *not* build: a token price model, user accounts, alerts, yield-curve twists. We chose one
> transparent, deterministic engine because a risk committee has to audit every assumption, and every assumption is
> on the Methodology page and editable.
>
> Next: ingest attestations automatically, alert when a new report moves a coin's breaking point, and sell it as a
> subscription to payment institutions and exchanges setting stablecoin limits."

## 7:30-8:00 · Close (Speaker A)

> "A backing ratio tells you how much is in the vault. PegGuard tells you whether it gets out in time. Thank you."
