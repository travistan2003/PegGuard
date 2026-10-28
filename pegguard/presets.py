"""Load the bundled reserve presets (data/presets.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .reserves import Portfolio, ReserveLine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRESETS_PATH = DATA_DIR / "presets.json"


@lru_cache(maxsize=1)
def _raw() -> list[dict]:
    with open(PRESETS_PATH, encoding="utf-8") as f:
        return json.load(f)["presets"]


def preset_ids() -> list[str]:
    return [p["id"] for p in _raw()]


def preset_names() -> dict[str, str]:
    return {p["id"]: p["name"] for p in _raw()}


def load_preset(preset_id: str) -> Portfolio:
    for p in _raw():
        if p["id"] == preset_id:
            return Portfolio(
                name=p["name"],
                supply_bn=float(p["supply_bn"]),
                lines=[ReserveLine(**l) for l in p["lines"]],
                description=p.get("description", ""),
                source=p.get("source", ""),
                as_of=p.get("as_of", ""),
            )
    raise KeyError(f"Unknown preset: {preset_id}")


def all_presets() -> list[Portfolio]:
    return [load_preset(i) for i in preset_ids()]
