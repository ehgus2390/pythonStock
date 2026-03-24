import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "krx_universe_cache.json"
SNAPSHOT_PATH = ROOT / "krx_universe_snapshot.csv"


def main() -> int:
    if not CACHE_PATH.exists():
        print(f"cache file not found: {CACHE_PATH}")
        print("run the app once on KR market to create cache, then run this script again.")
        return 1

    try:
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"failed to read cache: {e}")
        return 1

    by_exchange = data.get("by_exchange", {})
    rows = []
    for exch in ["KOSPI", "KOSDAQ", "KONEX"]:
        node = by_exchange.get(exch, {})
        rows.extend(node.get("rows", []) or [])

    if not rows:
        print("no rows in cache")
        return 1

    df = pd.DataFrame(rows)
    for col in ["name", "symbol", "exchange", "currency", "price"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["name", "symbol", "exchange", "currency", "price"]].drop_duplicates(subset=["symbol"])
    df.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    print(f"saved {len(df)} rows -> {SNAPSHOT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
