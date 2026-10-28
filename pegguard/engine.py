"""The stress engine: what happens to a fiat-backed stablecoin's reserves during a run.

Timeline
--------
Day 0  Shocks hit instantly:
       * a parallel interest-rate shock reprices bills and notes (Week 3 bond maths)
       * gold / crypto / risk-asset price shocks and a credit loss on secured loans
       * an optional bank failure freezes part of the cash held at banks (USDC/SVB, March 2023)
Day 1..H  Holders ask to redeem. The issuer pays $1 per token, raising cash through a
       liquidity waterfall: cash, repo, money market fund, bills (shortest first), notes,
       gold, crypto, other, loans. Each asset can only be sold up to its daily liquidity and
       sales below cash pay a fire-sale discount. Requests it cannot meet are queued.

Optional panic feedback (Diamond & Dybvig 1983): when reserves fall below the tokens
outstanding, paying early redeemers $1 leaves *less* for everyone else, so redemptions
accelerate.

Outputs
-------
A daily table plus a summary: coverage ratio (reserves / tokens), implied value per token,
fire-sale losses, unmet redemptions and an overall verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable

import numpy as np
import pandas as pd

from .pricing import reprice_factor
from .reserves import ASSET_CLASSES, ReserveLine

PAR_TOL = 0.9995  # coverage below this is treated as "below par"
MMF_BREAK_THE_BUCK = 0.995


@dataclass
class Scenario:
    name: str = "Custom"
    rate_shock_bp: float = 0.0
    redemption_pct: float = 20.0  # % of starting supply that asks to redeem over the horizon
    horizon_days: int = 10  # business days
    front_load: float = 0.35  # 0 = evenly spread; higher = more of the run on day 1
    bank_freeze_pct: float = 0.0  # % of bank cash frozen in a bank failure
    frozen_recovery_pct: float = 100.0  # expected recovery on frozen cash (for valuation)
    stress_multiplier: float = 1.0  # scales every fire-sale discount
    gold_shock_pct: float = 0.0  # e.g. -10
    crypto_shock_pct: float = 0.0  # e.g. -30
    risk_shock_pct: float = 0.0  # equities / other investments
    loan_loss_pct: float = 0.0  # credit loss on secured loans
    panic_sensitivity: float = 0.0  # extra redemptions per 1pp of under-coverage (0.2 = +20%)

    def schedule(self) -> np.ndarray:
        """Share of the base run that arrives on each day (sums to 1)."""
        h = max(1, int(self.horizon_days))
        decay = 1.0 - min(max(self.front_load, 0.0), 0.95)
        w = decay ** np.arange(h)
        return w / w.sum()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StressResult:
    daily: pd.DataFrame
    by_holding: pd.DataFrame
    summary: dict
    scenario: Scenario
    supply0: float
    reserves0: float

    @property
    def verdict(self) -> str:
        return self.summary["verdict"]


def _price_shock(line: ReserveLine, sc: Scenario) -> float:
    key = line.spec.shock_key
    if key == "gold":
        return 1 + sc.gold_shock_pct / 100
    if key == "crypto":
        return 1 + sc.crypto_shock_pct / 100
    if key == "risk":
        return 1 + sc.risk_shock_pct / 100
    if key == "credit":
        return 1 - abs(sc.loan_loss_pct) / 100
    return 1.0


def _rate_factor(line: ReserveLine, sc: Scenario) -> float:
    kind = line.spec.rate_kind
    if kind == "none":
        return 1.0
    f = reprice_factor("zero" if kind in ("zero", "mmf") else "coupon",
                       line.maturity_years, line.yield_pct / 100, sc.rate_shock_bp / 10_000)
    if kind == "mmf":
        # Stable-NAV government MMFs hold their $1.00 price unless the shadow NAV
        # falls below $0.995 ("breaking the buck").
        return 1.0 if f >= MMF_BREAK_THE_BUCK else f
    return f


def _waterfall_order(lines: list[ReserveLine]) -> list[int]:
    return sorted(range(len(lines)), key=lambda i: (lines[i].spec.rank, lines[i].maturity_years))


def run_stress(lines: Iterable[ReserveLine], supply_bn: float, sc: Scenario) -> StressResult:
    lines = [l for l in lines if l.amount_bn > 0]
    supply0 = float(supply_bn)
    reserves0 = float(sum(l.amount_bn for l in lines))
    n = len(lines)

    # ---- Day 0: shocks -------------------------------------------------------------
    value = np.zeros(n)
    rate_loss = np.zeros(n)
    price_loss = np.zeros(n)
    frozen = np.zeros(n)  # face value of frozen bank cash
    for i, l in enumerate(lines):
        after_rate = l.amount_bn * _rate_factor(l, sc)
        after_price = after_rate * _price_shock(l, sc)
        rate_loss[i] = l.amount_bn - after_rate
        price_loss[i] = after_rate - after_price
        value[i] = after_price
        if l.asset_class == "cash_bank" and sc.bank_freeze_pct > 0:
            frozen[i] = value[i] * min(sc.bank_freeze_pct, 100) / 100
            value[i] -= frozen[i]

    recovery = min(max(sc.frozen_recovery_pct, 0), 100) / 100
    frozen_value = float(frozen.sum() * recovery)
    capacity = np.array([max(value[i] * lines[i].liquidity, 0.0) for i in range(n)])
    discount = np.array([min(l.fire_sale * max(sc.stress_multiplier, 0.0), 0.95) for l in lines])
    order = _waterfall_order(lines)

    supply = supply0
    reserves = float(value.sum() + frozen_value)
    coverage = reserves / supply if supply > 0 else float("nan")
    sold = np.zeros(n)
    fire_loss = np.zeros(n)

    rows = [
        dict(day=0, new_requests=0.0, queued_in=0.0, requested=0.0, paid=0.0, unmet=0.0,
             fire_sale_loss=0.0, supply=supply, reserves=reserves, liquid_next_day=float(capacity.sum()),
             coverage=coverage, panic_multiplier=1.0)
    ]

    base = sc.redemption_pct / 100 * supply0 * sc.schedule()
    queue = 0.0
    total_paid = 0.0
    total_requested = 0.0
    first_breach_day = None

    for d in range(1, len(base) + 1):
        under = max(0.0, 1.0 - coverage) if np.isfinite(coverage) else 0.0
        panic = 1.0 + sc.panic_sensitivity * under * 100
        new_req = min(base[d - 1] * panic, max(supply - queue, 0.0))
        requested = new_req + queue
        total_requested += new_req

        need = requested
        day_loss = 0.0
        for i in order:
            if need <= 1e-12:
                break
            avail = min(capacity[i], value[i])
            if avail <= 1e-12:
                continue
            net = 1.0 - discount[i]
            sell = min(avail, need / net)
            proceeds = sell * net
            value[i] -= sell
            sold[i] += sell
            fire_loss[i] += sell - proceeds
            day_loss += sell - proceeds
            need -= proceeds
        paid = requested - max(need, 0.0)
        queue = requested - paid
        if queue > 1e-9 and first_breach_day is None:
            first_breach_day = d
        supply -= paid
        total_paid += paid
        reserves = float(value.sum() + frozen_value)
        coverage = reserves / supply if supply > 1e-9 else float("nan")
        # liquidity capacity resets each day, capped by what is left
        liquid_next = float(np.minimum(capacity, value).sum())
        rows.append(
            dict(day=d, new_requests=new_req, queued_in=requested - new_req, requested=requested,
                 paid=paid, unmet=queue, fire_sale_loss=day_loss, supply=supply, reserves=reserves,
                 liquid_next_day=liquid_next, coverage=coverage, panic_multiplier=panic)
        )

    daily = pd.DataFrame(rows)
    cov = daily["coverage"].replace([np.inf, -np.inf], np.nan)
    min_cov = float(cov.min()) if cov.notna().any() else float("nan")
    final_cov = float(cov.dropna().iloc[-1]) if cov.notna().any() else float("nan")

    by_holding = pd.DataFrame(
        {
            "Holding": [l.name for l in lines],
            "Asset class": [l.spec.label for l in lines],
            "Start ($bn)": [l.amount_bn for l in lines],
            "Rate loss ($bn)": rate_loss,
            "Price/credit loss ($bn)": price_loss,
            "Frozen ($bn)": frozen,
            "Sold ($bn)": sold,
            "Fire-sale loss ($bn)": fire_loss,
            "End ($bn)": value,
            "color": [l.spec.color for l in lines],
        }
    )

    unmet_final = float(queue)
    below_par = min_cov < PAR_TOL
    breach = first_breach_day is not None
    if below_par and breach:
        verdict = "BREAKS"
        headline = "Reserves fall below par and redemptions cannot be met on time."
    elif below_par:
        verdict = "BELOW PAR"
        headline = "Every redemption is paid, but reserves end up worth less than the tokens outstanding."
    elif breach:
        verdict = "LIQUIDITY STRAIN"
        headline = "Solvent, but the issuer cannot raise cash fast enough to pay everyone on time."
    else:
        verdict = "HOLDS"
        headline = "Every redemption is paid at $1 and reserves stay at or above par."

    # Loss pushed onto holders who did not redeem (first-mover advantage, Diamond & Dybvig)
    stayers_loss = max(0.0, (1 - final_cov) * supply) if np.isfinite(final_cov) else 0.0

    summary = dict(
        verdict=verdict,
        headline=headline,
        start_coverage=reserves0 / supply0 if supply0 > 0 else float("nan"),
        day0_coverage=float(daily.loc[0, "coverage"]),
        min_coverage=min_cov,
        final_coverage=final_cov,
        implied_token_value=min(1.0, final_cov) if np.isfinite(final_cov) else float("nan"),
        min_token_value=min(1.0, min_cov) if np.isfinite(min_cov) else float("nan"),
        rate_loss=float(rate_loss.sum()),
        price_loss=float(price_loss.sum()),
        frozen=float(frozen.sum()),
        frozen_writedown=float(frozen.sum() * (1 - recovery)),
        fire_sale_loss=float(fire_loss.sum()),
        total_loss=float(rate_loss.sum() + price_loss.sum() + frozen.sum() * (1 - recovery) + fire_loss.sum()),
        requested=total_requested,
        paid=total_paid,
        unmet=unmet_final,
        first_breach_day=first_breach_day,
        stayers_loss=stayers_loss,
        supply_end=supply,
        reserves_end=reserves,
    )
    return StressResult(daily=daily, by_holding=by_holding, summary=summary, scenario=sc,
                        supply0=supply0, reserves0=reserves0)


def redemption_capacity(lines: Iterable[ReserveLine], days: int = 5, stress_multiplier: float = 1.0,
                        sc: Scenario | None = None) -> float:
    """Cash ($bn) the issuer could raise within `days` business days, after any day-0 shocks."""
    sc = sc or Scenario(redemption_pct=0)
    total = 0.0
    for l in lines:
        v = l.amount_bn * _rate_factor(l, sc) * _price_shock(l, sc)
        if l.asset_class == "cash_bank" and sc.bank_freeze_pct > 0:
            v *= 1 - min(sc.bank_freeze_pct, 100) / 100
        sellable = min(v, v * l.liquidity * days)
        disc = min(l.fire_sale * max(stress_multiplier, 0.0), 0.95)
        total += sellable * (1 - disc)
    return total
