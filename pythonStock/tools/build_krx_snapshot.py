import json
import re
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "krx_universe_cache.json"
SNAPSHOT_PATH = ROOT / "krx_universe_snapshot.csv"


def _rows_from_cache() -> list[dict]:
    if not CACHE_PATH.exists():
        return []
    try:
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    rows: list[dict] = []
    by_exchange = data.get("by_exchange", {})
    for exch in ["KOSPI", "KOSDAQ", "KONEX"]:
        node = by_exchange.get(exch, {})
        rows.extend(node.get("rows", []) or [])
    return rows


def _rows_from_kind() -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://kind.krx.co.kr/",
    }
    rows: list[dict] = []
    market_map = [("stockMkt", "KOSPI", ".KS"), ("kosdaqMkt", "KOSDAQ", ".KQ"), ("konexMkt", "KONEX", ".KQ")]

    for market_type, exch, suffix in market_map:
        try:
            url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={market_type}"
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
        except Exception:
            continue

        matches = re.findall(r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>.*?<td[^>]*>(\d{6})</td>", resp.text, flags=re.S)
        for name, code in matches:
            nm = str(name).strip()
            cd = str(code).strip().zfill(6)
            if nm and len(cd) == 6 and cd.isdigit():
                rows.append(
                    {
                        "name": nm,
                        "symbol": f"{cd}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )
    return rows


def _rows_from_naver() -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.naver.com/",
    }
    rows: list[dict] = []
    market_map = [(0, "KOSPI", ".KS"), (1, "KOSDAQ", ".KQ")]

    for sosok, exch, suffix in market_map:
        try:
            first_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
            resp = requests.get(first_url, headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = "euc-kr"
        except Exception:
            continue

        pages = [int(x) for x in re.findall(r"page=(\d+)", resp.text)]
        max_page = min(max(pages) if pages else 1, 120)
        seen: set[str] = set()

        for page in range(1, max_page + 1):
            try:
                page_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                page_resp = requests.get(page_url, headers=headers, timeout=20)
                page_resp.raise_for_status()
                page_resp.encoding = "euc-kr"
            except Exception:
                continue

            for code, name in re.findall(r'/item/main\.naver\?code=(\d{6})"[^>]*>([^<]+)</a>', page_resp.text):
                cd = str(code).strip()
                nm = str(name).strip()
                if cd in seen or (not nm):
                    continue
                seen.add(cd)
                rows.append(
                    {
                        "name": nm,
                        "symbol": f"{cd}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )
    return rows


def main() -> int:
    rows = _rows_from_cache()
    source = "cache"
    if not rows:
        rows = _rows_from_kind()
        source = "kind"
    if not rows:
        rows = _rows_from_naver()
        source = "naver"
    if not rows:
        print("failed to build snapshot from cache, KRX KIND, and Naver")
        return 1

    df = pd.DataFrame(rows)
    for col in ["name", "symbol", "exchange", "currency", "price"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["name", "symbol", "exchange", "currency", "price"]].drop_duplicates(subset=["symbol"])
    df.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    print(f"saved {len(df)} rows from {source} -> {SNAPSHOT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
