"""Refresh the offline data bundled with the app. Run this once while online before a demo.

    python scripts/refresh_snapshot.py

It downloads (from free DefiLlama endpoints, no API key):
  * the live stablecoin supply table   -> data/snapshots/stablecoins.json and data/cache/
  * 90 days of daily peg prices        -> data/cache/price_history.json
  * hourly USDC prices, 9-17 Mar 2023  -> data/snapshots/usdc_svb_2023_hourly.csv
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pegguard import data_sources as ds  # noqa: E402


def main() -> None:
    ok = True
    df, meta = ds.load_stablecoins(live=True)
    if meta["mode"] == "live":
        shutil.copy(ds.CACHE_DIR / "stablecoins.json", ds.SNAPSHOT_DIR / "stablecoins.json")
        print(f"Stablecoins: {len(df)} USD stablecoins, total ${df['supply_usd'].sum() / 1e9:,.1f}bn")
    else:
        ok = False
        print(f"Stablecoins: live fetch failed, kept existing data ({meta['note']})")

    hist, meta = ds.load_price_history(days=90, live=True)
    print(f"Price history: {meta['mode']} ({len(hist)} rows)")
    ok &= meta["mode"] == "live"

    try:
        svb = ds.fetch_svb_hourly()
        if len(svb):
            svb.to_csv(ds.SNAPSHOT_DIR / "usdc_svb_2023_hourly.csv", index=False)
            print(f"SVB episode: {len(svb)} hourly prices, low ${svb['price'].min():.4f}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"SVB episode: fetch failed ({e})")

    print("\nDone." if ok else "\nDone with warnings: the app will fall back to the bundled data where needed.")


if __name__ == "__main__":
    main()
