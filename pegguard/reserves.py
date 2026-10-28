"""Reserve asset classes and the reserve portfolio data model.

Each asset class carries the assumptions the stress engine needs:

* daily_liquidity   share of the (post-shock) holding that can be turned into cash per day
* fire_sale_bps     discount paid when selling in a hurry, before the stress multiplier
* rate_kind         how a rate shock reprices it ("none", "zero" for bills, "coupon" for notes)
* shock_key         which scenario price shock applies (gold, crypto, risk assets, credit)
* genius / mas      whether it is an eligible reserve asset under simplified GENIUS Act /
                    MAS single-currency stablecoin rules (maturity limits are checked separately)
* rank              order in the redemption waterfall (lowest is used first)

These are deliberately simple, transparent defaults. Every one of them can be edited in the
app, and the methodology page explains where each comes from.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class AssetClass:
    key: str
    label: str
    daily_liquidity: float
    fire_sale_bps: float
    rate_kind: str  # none | zero | coupon | mmf
    shock_key: str | None
    genius: bool
    mas: bool
    rank: int
    default_maturity: float
    default_yield: float
    color: str
    note: str = ""


ASSET_CLASSES: dict[str, AssetClass] = {
    a.key: a
    for a in [
        AssetClass("cash_bank", "Cash at commercial banks", 1.00, 0, "none", None, True, True, 1, 0.0, 0.0,
                   "#0F766E", "Instantly available unless the bank fails (see bank-failure shock)."),
        AssetClass("repo", "Reverse repo (Treasury-collateralised)", 1.00, 0, "none", None, True, True, 2, 0.003, 4.0,
                   "#14B8A6", "Overnight repo matures every day, so it converts to cash at par."),
        AssetClass("mmf_gov", "Government money market fund", 0.60, 5, "mmf", None, True, True, 3, 0.08, 4.0,
                   "#2563EB", "Stable-NAV fund holding bills and repo. Large redemptions force the fund to sell bills."),
        AssetClass("tbill", "US Treasury bills", 0.50, 10, "zero", None, True, True, 4, 0.25, 4.0,
                   "#60A5FA", "Deepest market in the world, but very large same-day sales still move the price."),
        AssetClass("tnote", "Treasury notes / bonds (> 1y)", 0.25, 50, "coupon", None, False, False, 5, 5.0, 4.0,
                   "#7C3AED", "Rate-sensitive. This is where an SVB-style duration loss comes from."),
        AssetClass("gold", "Gold", 0.20, 100, "none", "gold", False, False, 6, 0.0, 0.0,
                   "#D97706", "Price risk plus a wider bid-ask in stress."),
        AssetClass("crypto", "Bitcoin / crypto", 0.20, 300, "none", "crypto", False, False, 7, 0.0, 0.0,
                   "#EA580C", "Volatile, and falls hardest exactly when stablecoin runs happen."),
        AssetClass("other", "Other investments / equities", 0.10, 500, "none", "risk", False, False, 8, 0.0, 0.0,
                   "#DB2777", "Hard to value and slow to sell."),
        AssetClass("secured_loan", "Secured loans", 0.02, 1000, "none", "credit", False, False, 9, 0.0, 0.0,
                   "#DC2626", "Effectively locked up: can only be recalled or sold at a steep discount."),
    ]
}

CLASS_KEYS = list(ASSET_CLASSES)
LABEL_TO_KEY = {a.label: a.key for a in ASSET_CLASSES.values()}


@dataclass
class ReserveLine:
    name: str
    asset_class: str
    amount_bn: float
    maturity_years: float = 0.0
    yield_pct: float = 0.0
    # Optional per-line overrides (None means use the asset-class default)
    daily_liquidity: float | None = None
    fire_sale_bps: float | None = None

    @property
    def spec(self) -> AssetClass:
        return ASSET_CLASSES[self.asset_class]

    @property
    def liquidity(self) -> float:
        return self.spec.daily_liquidity if self.daily_liquidity is None else float(self.daily_liquidity)

    @property
    def fire_sale(self) -> float:
        bps = self.spec.fire_sale_bps if self.fire_sale_bps is None else float(self.fire_sale_bps)
        return bps / 10_000.0


@dataclass
class Portfolio:
    name: str
    supply_bn: float
    lines: list[ReserveLine] = field(default_factory=list)
    description: str = ""
    source: str = ""
    as_of: str = ""

    @property
    def reserves_bn(self) -> float:
        return float(sum(l.amount_bn for l in self.lines))

    @property
    def backing_ratio(self) -> float:
        return self.reserves_bn / self.supply_bn if self.supply_bn > 0 else float("nan")

    def to_frame(self) -> pd.DataFrame:
        return lines_to_frame(self.lines)


EDITOR_COLUMNS = ["Holding", "Asset class", "Amount ($bn)", "Maturity (yrs)", "Yield (%)"]


def lines_to_frame(lines: Iterable[ReserveLine]) -> pd.DataFrame:
    rows = [
        {
            "Holding": l.name,
            "Asset class": ASSET_CLASSES[l.asset_class].label,
            "Amount ($bn)": float(l.amount_bn),
            "Maturity (yrs)": float(l.maturity_years),
            "Yield (%)": float(l.yield_pct),
        }
        for l in lines
    ]
    return pd.DataFrame(rows, columns=EDITOR_COLUMNS)


def frame_to_lines(df: pd.DataFrame) -> list[ReserveLine]:
    """Convert the app's editable table back into reserve lines, skipping blank or invalid rows."""
    out: list[ReserveLine] = []
    for _, r in df.iterrows():
        label = r.get("Asset class")
        key = LABEL_TO_KEY.get(label, label if label in ASSET_CLASSES else None)
        try:
            amt = float(r.get("Amount ($bn)") or 0.0)
        except (TypeError, ValueError):
            amt = 0.0
        if key is None or amt <= 0:
            continue
        spec = ASSET_CLASSES[key]
        mat = r.get("Maturity (yrs)")
        yld = r.get("Yield (%)")
        out.append(
            ReserveLine(
                name=str(r.get("Holding") or spec.label),
                asset_class=key,
                amount_bn=amt,
                maturity_years=float(spec.default_maturity if pd.isna(mat) else mat),
                yield_pct=float(spec.default_yield if pd.isna(yld) else yld),
            )
        )
    return out


def composition(lines: Iterable[ReserveLine]) -> pd.DataFrame:
    """Reserve mix by asset class (amount and share)."""
    lines = list(lines)
    total = sum(l.amount_bn for l in lines) or 1.0
    agg: dict[str, float] = {}
    for l in lines:
        agg[l.asset_class] = agg.get(l.asset_class, 0.0) + l.amount_bn
    rows = [
        {
            "key": k,
            "Asset class": ASSET_CLASSES[k].label,
            "Amount ($bn)": v,
            "Share": v / total,
            "color": ASSET_CLASSES[k].color,
        }
        for k, v in sorted(agg.items(), key=lambda kv: ASSET_CLASSES[kv[0]].rank)
    ]
    return pd.DataFrame(rows)


def portfolio_to_dict(p: Portfolio) -> dict:
    d = asdict(p)
    return d
