"""Higher-level analysis built on the stress engine.

* breaking_point_grid   run the engine across rate shocks x run sizes (the "where does it break" map)
* survival_frontier     largest run survivable at each rate shock
* standard_scenarios    a fixed scenario library so different coins can be compared like for like
* regulatory_check      simplified GENIUS Act / MAS SCS reserve eligibility test
* risk_profile          duration, weighted maturity and liquidity ladder of the reserves
* position_outcome      what a stress run means for one holder's position: loss if held, days to exit if redeemed
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import numpy as np
import pandas as pd

from .engine import PAR_TOL, Scenario, redemption_capacity, run_stress
from .pricing import modified_duration
from .reserves import ASSET_CLASSES, ReserveLine

# --------------------------------------------------------------------------------------
# Scenario library
# --------------------------------------------------------------------------------------

STANDARD_SCENARIOS: list[Scenario] = [
    Scenario(name="Calm: normal redemptions", rate_shock_bp=0, redemption_pct=5, horizon_days=5,
             front_load=0.2),
    Scenario(name="Rate shock: +300bp, 20% run", rate_shock_bp=300, redemption_pct=20, horizon_days=5,
             front_load=0.35, stress_multiplier=2),
    Scenario(name="Crypto crash: BTC -50%, 30% run", rate_shock_bp=0, redemption_pct=30, horizon_days=5,
             front_load=0.4, crypto_shock_pct=-50, gold_shock_pct=-10, risk_shock_pct=-30,
             loan_loss_pct=10, stress_multiplier=3),
    Scenario(name="Bank failure: 30% of bank cash frozen", bank_freeze_pct=30, frozen_recovery_pct=0,
             redemption_pct=25, horizon_days=5, front_load=0.5, stress_multiplier=2),
    Scenario(name="Full panic: 50% run in 5 days", rate_shock_bp=150, redemption_pct=50, horizon_days=5,
             front_load=0.5, stress_multiplier=3, crypto_shock_pct=-40, gold_shock_pct=-10,
             risk_shock_pct=-30, loan_loss_pct=15, panic_sensitivity=0.3),
]


def run_library(lines: list[ReserveLine], supply: float,
                scenarios: Iterable[Scenario] = STANDARD_SCENARIOS) -> pd.DataFrame:
    rows = []
    for sc in scenarios:
        r = run_stress(lines, supply, sc).summary
        rows.append(
            {
                "Scenario": sc.name,
                "Verdict": r["verdict"],
                "Lowest coverage": r["min_coverage"],
                "Value per token": r["min_token_value"],
                "Total loss ($bn)": r["total_loss"],
                "Unmet redemptions ($bn)": r["unmet"],
                "First late day": r["first_breach_day"],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Breaking-point map
# --------------------------------------------------------------------------------------

def breaking_point_grid(
    lines: list[ReserveLine],
    supply: float,
    base: Scenario,
    rate_shocks_bp: Iterable[float] = range(0, 525, 25),
    run_sizes_pct: Iterable[float] = range(0, 105, 5),
) -> pd.DataFrame:
    """Run the engine for every (rate shock, run size) pair, keeping all other settings from `base`."""
    rows = []
    for bp in rate_shocks_bp:
        for run in run_sizes_pct:
            sc = replace(base, rate_shock_bp=float(bp), redemption_pct=float(run))
            s = run_stress(lines, supply, sc).summary
            rows.append(
                {
                    "rate_shock_bp": float(bp),
                    "run_pct": float(run),
                    "min_coverage": s["min_coverage"],
                    "unmet": s["unmet"],
                    "late": s["first_breach_day"] is not None,
                    "below_par": s["min_coverage"] < PAR_TOL,
                    "verdict": s["verdict"],
                }
            )
    return pd.DataFrame(rows)


def survival_frontier(grid: pd.DataFrame) -> pd.DataFrame:
    """For each rate shock: the largest run that is still paid on time, and still at par."""
    out = []
    for bp, g in grid.groupby("rate_shock_bp"):
        g = g.sort_values("run_pct")
        ok_liq = g.loc[~g["late"], "run_pct"]
        ok_par = g.loc[~g["below_par"], "run_pct"]
        ok_all = g.loc[~g["late"] & ~g["below_par"], "run_pct"]
        out.append(
            {
                "rate_shock_bp": bp,
                "max_run_paid_on_time": float(ok_liq.max()) if len(ok_liq) else 0.0,
                "max_run_at_par": float(ok_par.max()) if len(ok_par) else float("nan"),
                "max_run_holds": float(ok_all.max()) if len(ok_all) else float("nan"),
            }
        )
    return pd.DataFrame(out)


# --------------------------------------------------------------------------------------
# Regulation (simplified, educational)
# --------------------------------------------------------------------------------------

GENIUS_MAX_BILL_YEARS = 93 / 365  # GENIUS Act: T-bills with maturity of 93 days or less
GENIUS_MAX_REPO_YEARS = 7 / 365  # repo with maturity of 7 days or less
MAS_MAX_YEARS = 0.25  # MAS SCS framework: short-dated (<= 3 months) government debt


def _eligible(line: ReserveLine, regime: str) -> tuple[bool, str]:
    spec = line.spec
    if regime == "GENIUS":
        if not spec.genius:
            return False, "Not permitted"
        if line.asset_class == "tbill" and line.maturity_years > GENIUS_MAX_BILL_YEARS + 1e-9:
            return False, "Bill > 93 days"
        if line.asset_class == "repo" and line.maturity_years > GENIUS_MAX_REPO_YEARS + 1e-9:
            return False, "Repo > 7 days"
        return True, "Eligible"
    if not spec.mas:
        return False, "Not very-low-risk"
    if line.asset_class in ("tbill", "repo") and line.maturity_years > MAS_MAX_YEARS + 1e-9:
        return False, "Maturity > 3 months"
    return True, "Eligible"


def regulatory_check(lines: list[ReserveLine], supply: float) -> dict:
    total = sum(l.amount_bn for l in lines)
    out = {}
    for regime in ("GENIUS", "MAS"):
        detail = []
        eligible_amt = 0.0
        for l in lines:
            ok, why = _eligible(l, regime)
            if ok:
                eligible_amt += l.amount_bn
            detail.append({"Holding": l.name, "Amount ($bn)": l.amount_bn, "Eligible": ok, "Reason": why})
        out[regime] = {
            "eligible_bn": eligible_amt,
            "eligible_share": eligible_amt / total if total else float("nan"),
            "eligible_backing": eligible_amt / supply if supply else float("nan"),
            "passes": eligible_amt / supply >= 1.0 - 1e-9 if supply else False,
            "detail": pd.DataFrame(detail),
        }
    return out


# --------------------------------------------------------------------------------------
# Risk profile
# --------------------------------------------------------------------------------------

def risk_profile(lines: list[ReserveLine], supply: float) -> dict:
    total = sum(l.amount_bn for l in lines) or 1.0
    dur = 0.0
    wam = 0.0
    for l in lines:
        kind = l.spec.rate_kind
        if kind != "none":
            k = "zero" if kind in ("zero", "mmf") else "coupon"
            dur += l.amount_bn / total * modified_duration(k, l.maturity_years, l.yield_pct / 100)
            wam += l.amount_bn / total * l.maturity_years
    cap1 = redemption_capacity(lines, days=1)
    cap5 = redemption_capacity(lines, days=5)
    ladder = pd.DataFrame(
        [{"Days": d, "Cash raisable ($bn)": redemption_capacity(lines, days=d),
          "Share of supply": redemption_capacity(lines, days=d) / supply if supply else np.nan}
         for d in (1, 2, 3, 5, 10, 20)]
    )
    return {
        "duration": dur,
        "wam_days": wam * 365,
        "dv01_bn": dur * total / 10_000,  # $bn lost per +1bp
        "loss_per_100bp_pct": dur,  # % of reserves lost per +100bp (approx)
        "day1_capacity_share": cap1 / supply if supply else np.nan,
        "day5_capacity_share": cap5 / supply if supply else np.nan,
        "ladder": ladder,
    }


# --------------------------------------------------------------------------------------
# Position view (for a holder of the token)
# --------------------------------------------------------------------------------------

def exit_timing(daily: pd.DataFrame) -> tuple[int | None, float]:
    """When a holder who asks to redeem on day 1 is paid in full.

    The queue is first in, first out, so day-1 requests are paid before anything filed later. Returns
    (first day fully paid or None, share of the day-1 request paid by the end of the horizon). The holder's own
    request is assumed small next to the run, so it does not change the run itself.
    """
    run = daily[daily["day"] > 0]
    if run.empty:
        return None, float("nan")
    first = float(run["new_requests"].iloc[0])
    if first <= 1e-12:
        # Nobody else is redeeming: paid on day 1 if anything can be sold that day.
        return (1, 1.0) if float(daily["liquid_next_day"].iloc[0]) > 0 else (None, 0.0)
    cum_paid = run["paid"].cumsum().to_numpy()
    done = np.nonzero(cum_paid >= first * (1 - 1e-9))[0]
    day_full = int(run["day"].iloc[done[0]]) if len(done) else None
    return day_full, min(1.0, float(cum_paid[-1]) / first)


def position_outcome(summary: dict, daily: pd.DataFrame, position: float) -> dict:
    """Translate a stress run into P&L for a position of `position` (any currency unit) in the token.

    * hold:   marked at the worst value per token during the run (what you could lose by staying in)
    * redeem: ask for $1 on day 1; paid in full on `exit_day`, or only `exit_share_paid` by the end
    """
    worst = summary["min_token_value"]
    haircut = 0.0 if not np.isfinite(worst) else max(0.0, 1.0 - worst)
    day_full, share = exit_timing(daily)
    return {
        "position": position,
        "hold_value": position * (1 - haircut),
        "hold_loss": position * haircut,
        "haircut_bp": haircut * 10_000,
        "exit_day": day_full,
        "exit_share_paid": share,
    }
