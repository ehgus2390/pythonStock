import datetime as dt
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

try:
    from pykrx import stock as krx_stock

    KRX_AVAILABLE = True
except ModuleNotFoundError:
    krx_stock = None
    KRX_AVAILABLE = False

try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ModuleNotFoundError:
    fdr = None
    FDR_AVAILABLE = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    go = None
    make_subplots = None
    PLOTLY_AVAILABLE = False

try:
    from src.model_forecast import build_ml_forecast

    ML_FORECAST_AVAILABLE = True
except Exception:
    build_ml_forecast = None
    ML_FORECAST_AVAILABLE = False

try:
    _yf_cache = Path(__file__).resolve().parent / ".cache" / "yfinance"
    _yf_cache.mkdir(parents=True, exist_ok=True)
    if hasattr(yf, "set_tz_cache_location"):
        yf.set_tz_cache_location(str(_yf_cache))
except Exception:
    pass


st.set_page_config(page_title="Python Stock", layout="wide")
st.title("주식 분석 웹 (차트 + RSI + 매수/매도 신호 + 테마 + 1~3개월 예측)")


NAME_ALIASES = {
    "apple": "AAPL",
    "애플": "AAPL",
    "tesla": "TSLA",
    "테슬라": "TSLA",
    "nvidia": "NVDA",
    "엔비디아": "NVDA",
    "microsoft": "MSFT",
    "마이크로소프트": "MSFT",
    "삼성전자": "005930.KS",
    "카카오": "035720.KS",
    "네이버": "035420.KS",
    "현대차": "005380.KS",
    "셀트리온": "068270.KS",
}

THEME_OPTIONS = [
    "없음",
    "로봇",
    "방산",
    "반도체",
    "항공/우주",
    "AI/소프트웨어",
    "2차전지/배터리",
    "전기차",
    "바이오/제약",
    "게임/콘텐츠",
    "인터넷/플랫폼",
    "통신/5G",
    "에너지/원전",
    "금융/은행",
    "철강/소재",
    "건설/인프라",
    "해운/물류",
    "소비재/유통",
]
FORECAST_MODELS = {
    "Baseline(추세)": "baseline",
    "ML-Ridge": "ridge",
    "ML-RandomForest": "rf",
}

THEME_KEYWORDS = {
    "로봇": ["로봇", "robot", "automation", "자동화"],
    "방산": ["방산", "defense", "defence", "military", "무기"],
    "반도체": ["반도체", "semiconductor", "chip", "chips", "fab"],
    "항공/우주": ["항공", "우주", "aerospace", "space", "aviation"],
    "AI/소프트웨어": ["ai", "artificial intelligence", "software", "cloud", "saas", "인공지능", "소프트웨어", "클라우드"],
    "2차전지/배터리": ["2차전지", "배터리", "battery", "cathode", "anode", "lithium"],
    "전기차": ["전기차", "ev", "electric vehicle", "자동차", "auto", "vehicle"],
    "바이오/제약": ["바이오", "제약", "pharma", "biotech", "drug", "health"],
    "게임/콘텐츠": ["게임", "game", "entertainment", "media", "content", "콘텐츠"],
    "인터넷/플랫폼": ["인터넷", "platform", "portal", "e-commerce", "커머스", "플랫폼"],
    "통신/5G": ["통신", "telecom", "5g", "network", "네트워크"],
    "에너지/원전": ["에너지", "원전", "nuclear", "solar", "wind", "power", "utility"],
    "금융/은행": ["금융", "은행", "bank", "financial", "insurance", "증권"],
    "철강/소재": ["철강", "소재", "steel", "metal", "chemical", "material"],
    "건설/인프라": ["건설", "infrastructure", "engineering", "cement", "플랜트"],
    "해운/물류": ["해운", "물류", "shipping", "logistics", "transport"],
    "소비재/유통": ["유통", "retail", "consumer", "food", "beverage", "화장품"],
}

THEME_KR_SEEDS = {
    "로봇": ["휴림로봇", "레인보우로보틱스", "로보로보", "로보티즈", "에브리봇", "유진로봇"],
    "방산": ["한화에어로스페이스", "한국항공우주", "LIG넥스원", "현대로템", "풍산", "빅텍"],
    "반도체": ["삼성전자", "SK하이닉스", "한미반도체", "DB하이텍", "주성엔지니어링", "원익IPS"],
    "항공/우주": ["한화에어로스페이스", "한국항공우주", "쎄트렉아이", "AP위성", "인텔리안테크", "제노코"],
    "AI/소프트웨어": ["네이버", "카카오", "더존비즈온", "솔트룩스", "코난테크놀로지"],
    "2차전지/배터리": ["LG에너지솔루션", "삼성SDI", "에코프로", "에코프로비엠", "포스코퓨처엠"],
    "전기차": ["현대차", "기아", "만도", "HL만도", "명신산업"],
    "바이오/제약": ["셀트리온", "삼성바이오로직스", "유한양행", "한미약품", "SK바이오사이언스"],
    "게임/콘텐츠": ["엔씨소프트", "넷마블", "크래프톤", "펄어비스", "카카오게임즈"],
    "인터넷/플랫폼": ["네이버", "카카오", "쿠팡", "NHN", "다날"],
    "통신/5G": ["SK텔레콤", "KT", "LG유플러스", "케이엠더블유", "쏠리드"],
    "에너지/원전": ["한국전력", "두산에너빌리티", "한전기술", "한전KPS", "씨에스윈드"],
    "금융/은행": ["KB금융", "신한지주", "하나금융지주", "우리금융지주", "삼성화재"],
    "철강/소재": ["POSCO홀딩스", "현대제철", "동국제강", "롯데케미칼", "금호석유"],
    "건설/인프라": ["삼성물산", "현대건설", "DL이앤씨", "GS건설", "대우건설"],
    "해운/물류": ["HMM", "팬오션", "대한해운", "CJ대한통운", "한진"],
    "소비재/유통": ["아모레퍼시픽", "LG생활건강", "이마트", "롯데쇼핑", "CJ제일제당"],
}

THEME_US_SEEDS = {
    "로봇": ["ISRG", "ROK", "ABB", "SYM", "TER"],
    "방산": ["LMT", "NOC", "RTX", "GD", "LHX"],
    "반도체": ["NVDA", "AMD", "TSM", "AVGO", "INTC", "QCOM"],
    "항공/우주": ["BA", "RKLB", "SPCE", "LMT", "NOC", "RTX"],
    "AI/소프트웨어": ["MSFT", "GOOGL", "META", "ORCL", "CRM", "PLTR"],
    "2차전지/배터리": ["TSLA", "ALB", "QS", "ENVX", "LTHM"],
    "전기차": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "GM", "F"],
    "바이오/제약": ["LLY", "JNJ", "PFE", "MRNA", "REGN", "AMGN"],
    "게임/콘텐츠": ["EA", "TTWO", "RBLX", "NFLX", "DIS", "WBD"],
    "인터넷/플랫폼": ["AMZN", "META", "GOOGL", "UBER", "ABNB", "SHOP"],
    "통신/5G": ["VZ", "T", "TMUS", "ERIC", "NOK"],
    "에너지/원전": ["XOM", "CVX", "NEE", "DUK", "SMR", "CCJ"],
    "금융/은행": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
    "철강/소재": ["NUE", "X", "AA", "FCX", "CLF"],
    "건설/인프라": ["CAT", "DE", "URI", "VMC", "PWR"],
    "해운/물류": ["UPS", "FDX", "ZIM", "MATX"],
    "소비재/유통": ["WMT", "COST", "PG", "KO", "PEP", "MCD"],
}


APP_STATE_PATH = Path(__file__).resolve().parent / "user_state.json"


def load_user_state() -> dict:
    if not APP_STATE_PATH.exists():
        return {"recent": [], "favorites": []}
    try:
        with APP_STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        recent = data.get("recent", [])
        favorites = data.get("favorites", [])
        return {
            "recent": [str(x) for x in recent if str(x).strip()],
            "favorites": [str(x) for x in favorites if str(x).strip()],
        }
    except Exception:
        return {"recent": [], "favorites": []}


def save_user_state(state: dict) -> None:
    try:
        APP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with APP_STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def add_recent_symbol(state: dict, symbol: str, limit: int = 30) -> dict:
    sym = str(symbol).strip().upper()
    if not sym:
        return state
    recent = [sym] + [x for x in state.get("recent", []) if str(x).upper() != sym]
    state["recent"] = recent[:limit]
    return state


def convert_to_krw(price: float, currency: str, usdkrw: float | None) -> float | None:
    if price is None or pd.isna(price):
        return None
    cur = str(currency).upper()
    if cur in {"KRW", "KOR"}:
        return float(price)
    if cur in {"USD", "US$", "$"} and usdkrw is not None:
        return float(price) * float(usdkrw)
    return None


def get_company_name_by_symbol(symbol: str, market: str) -> str:
    sym = str(symbol).strip().upper()
    if not sym:
        return ""
    rows = get_krx_universe() if market == "KR" else get_us_universe()
    for row in rows:
        if str(row.get("symbol", "")).strip().upper() == sym:
            return str(row.get("name", "")).strip()
    return ""


@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_usdkrw_rate() -> float | None:
    try:
        fx = yf.download("KRW=X", period="5d", interval="1d", auto_adjust=False, progress=False)
        if fx is None or fx.empty:
            return None
        if isinstance(fx.columns, pd.MultiIndex):
            fx.columns = [x[0] for x in fx.columns]
        if "Close" not in fx.columns:
            return None
        return float(fx["Close"].dropna().iloc[-1])
    except Exception:
        return None

def dedupe_rows(rows: list[dict[str, str]], limit: int = 5000) -> list[dict[str, str]]:
    dedup = []
    seen = set()
    for item in rows:
        symbol = item.get("symbol", "")
        if not symbol:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        dedup.append(item)
        if len(dedup) >= limit:
            break
    return dedup


def filter_candidates_by_exchange(rows: list[dict[str, str]], market: str, exchange_choice: str) -> list[dict[str, str]]:
    if exchange_choice == "전체":
        return rows
    out = []
    for row in rows:
        exch = str(row.get("exchange", ""))
        if market == "KR":
            if exch == exchange_choice:
                out.append(row)
        else:
            if exch == exchange_choice:
                out.append(row)
    return out


def detect_theme(query: str) -> str:
    q = query.strip().lower()
    if not q:
        return "없음"
    for theme, keys in THEME_KEYWORDS.items():
        if any(k in q for k in keys):
            return theme
    return "없음"


@st.cache_data(show_spinner=False, ttl=60 * 10)
def get_krx_universe() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    if KRX_AVAILABLE:
        market_specs = [
            ("KOSPI", ".KS"),
            ("KOSDAQ", ".KQ"),
            ("KONEX", ".KQ"),
        ]
        for market_name, suffix in market_specs:
            try:
                tickers = krx_stock.get_market_ticker_list(market=market_name)
            except Exception:
                tickers = []
            for ticker in tickers:
                try:
                    name = krx_stock.get_market_ticker_name(ticker)
                except Exception:
                    continue
                if not name:
                    continue
                records.append(
                    {
                        "name": str(name).strip(),
                        "symbol": f"{ticker}{suffix}",
                        "exchange": market_name,
                        "currency": "KRW",
                        "price": "-",
                    }
                )

    if (not records) and FDR_AVAILABLE:
        def _append_fdr_listing(df: pd.DataFrame, fallback_exch: str) -> None:
            if df is None or df.empty:
                return
            for _, row in df.iterrows():
                code = str(row.get("Code", "")).zfill(6)
                name = str(row.get("Name", "")).strip()
                market_name = str(row.get("Market", fallback_exch)).upper()
                if len(code) != 6 or not name:
                    continue
                if "KOSDAQ" in market_name:
                    suffix = ".KQ"
                    exch = "KOSDAQ"
                elif "KONEX" in market_name:
                    suffix = ".KQ"
                    exch = "KONEX"
                else:
                    suffix = ".KS"
                    exch = "KOSPI"
                records.append(
                    {
                        "name": name,
                        "symbol": f"{code}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )

        # Try broad KRX listing first.
        try:
            _append_fdr_listing(fdr.StockListing("KRX"), "KOSPI")
        except Exception:
            pass

        # Retry by each market to increase resilience when KRX endpoint is flaky.
        if not records:
            for m in ["KOSPI", "KOSDAQ", "KONEX"]:
                try:
                    _append_fdr_listing(fdr.StockListing(m), m)
                except Exception:
                    continue

    # 3rd fallback: KRX KIND downloadable corp list (works without pykrx/FDR).
    if not records:
        market_params = [
            ("stockMkt", "KOSPI", ".KS"),
            ("kosdaqMkt", "KOSDAQ", ".KQ"),
            ("konexMkt", "KONEX", ".KQ"),
        ]
        for market_type, exch, suffix in market_params:
            try:
                url = f"https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={market_type}"
                # KRX endpoint is often served as html table; read_html handles it well.
                table = pd.read_html(url, header=0)[0]
            except Exception:
                continue

            if table is None or table.empty:
                continue

            # Normalize expected Korean column names.
            col_name = None
            col_code = None
            for c in table.columns:
                cs = str(c).strip()
                if cs in ["회사명", "기업명"]:
                    col_name = c
                if cs in ["종목코드", "종목 코드", "코드"]:
                    col_code = c
            if col_name is None or col_code is None:
                continue

            for _, row in table.iterrows():
                name = str(row.get(col_name, "")).strip()
                code = str(row.get(col_code, "")).strip()
                code = code.zfill(6)
                if not name or len(code) != 6 or (not code.isdigit()):
                    continue
                records.append(
                    {
                        "name": name,
                        "symbol": f"{code}{suffix}",
                        "exchange": exch,
                        "currency": "KRW",
                        "price": "-",
                    }
                )

    # 4th fallback: Naver Finance market-cap pages (cloud에서 상대적으로 안정적).
    if not records:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.naver.com/",
        }

        def _append_from_naver_market(sosok: int, exch: str, suffix: str) -> None:
            try:
                first_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
                first_resp = requests.get(first_url, headers=headers, timeout=10)
                first_resp.raise_for_status()
                first_resp.encoding = "euc-kr"
                html = first_resp.text
            except Exception:
                return

            pages = [int(x) for x in re.findall(r"page=(\d+)", html)]
            max_page = min(max(pages) if pages else 1, 120)
            seen_codes: set[str] = set()

            for page in range(1, max_page + 1):
                try:
                    page_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                    resp = requests.get(page_url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    resp.encoding = "euc-kr"
                    page_html = resp.text
                except Exception:
                    continue

                matches = re.findall(r'/item/main\.naver\?code=(\d{6})"[^>]*>([^<]+)</a>', page_html)
                for code, name in matches:
                    code = str(code).strip()
                    name = str(name).strip()
                    if len(code) != 6 or (not code.isdigit()) or (not name):
                        continue
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    records.append(
                        {
                            "name": name,
                            "symbol": f"{code}{suffix}",
                            "exchange": exch,
                            "currency": "KRW",
                            "price": "-",
                        }
                    )

        _append_from_naver_market(sosok=0, exch="KOSPI", suffix=".KS")
        _append_from_naver_market(sosok=1, exch="KOSDAQ", suffix=".KQ")
    return dedupe_rows(records, limit=20000)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_us_universe() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    exchange_map = {
        "A": "NYSE American",
        "N": "NYSE",
        "P": "NYSE Arca",
        "Q": "NASDAQ",
        "V": "IEX",
        "Z": "BATS",
    }

    try:
        nasdaq_df = pd.read_csv("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", sep="|")
        nasdaq_df = nasdaq_df[nasdaq_df["Symbol"].notna()]
        nasdaq_df = nasdaq_df[nasdaq_df["Symbol"] != "File Creation Time"]
        for _, row in nasdaq_df.iterrows():
            symbol = str(row.get("Symbol", "")).strip().upper()
            if not symbol:
                continue
            records.append(
                {
                    "name": str(row.get("Security Name", symbol)).strip(),
                    "symbol": symbol,
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "price": "-",
                }
            )
    except Exception:
        pass

    try:
        other_df = pd.read_csv("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", sep="|")
        other_df = other_df[other_df["ACT Symbol"].notna()]
        other_df = other_df[other_df["ACT Symbol"] != "File Creation Time"]
        for _, row in other_df.iterrows():
            symbol = str(row.get("ACT Symbol", "")).strip().upper()
            if not symbol:
                continue
            exch_code = str(row.get("Exchange", "")).strip().upper()
            exchange = exchange_map.get(exch_code, exch_code or "US")
            records.append(
                {
                    "name": str(row.get("Security Name", symbol)).strip(),
                    "symbol": symbol,
                    "exchange": exchange,
                    "currency": "USD",
                    "price": "-",
                }
            )
    except Exception:
        pass

    return dedupe_rows(records, limit=20000)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def get_krx_index_constituents(index_key: str) -> list[dict[str, str]]:
    """
    index_key: 'KOSPI50' or 'KOSDAQ100'
    """
    target_name_map = {
        "KOSPI50": ["코스피 50", "코스피50", "KOSPI 50"],
        "KOSDAQ100": ["코스닥 100", "코스닥100", "KOSDAQ 100"],
    }
    target_market_map = {
        "KOSPI50": "KOSPI",
        "KOSDAQ100": "KOSDAQ",
    }
    target_size_map = {
        "KOSPI50": 50,
        "KOSDAQ100": 100,
    }

    rows = get_krx_universe()
    by_code = {}
    for r in rows:
        code = str(r.get("symbol", "")).split(".")[0]
        if len(code) == 6 and code.isdigit():
            by_code[code] = r

    out: list[dict[str, str]] = []
    code_set: set[str] = set()

    # 1) primary: pykrx index constituents
    if KRX_AVAILABLE:
        try:
            idx_markets = ["KOSPI", "KOSDAQ", "KRX", "테마"]
            matched_idx = None
            for mk in idx_markets:
                tickers = krx_stock.get_index_ticker_list(market=mk)
                for idx_t in tickers:
                    idx_name = krx_stock.get_index_ticker_name(idx_t)
                    if any(k in str(idx_name) for k in target_name_map.get(index_key, [])):
                        matched_idx = idx_t
                        break
                if matched_idx:
                    break

            if matched_idx:
                members = krx_stock.get_index_portfolio_deposit_file(matched_idx) or []
                for code in members:
                    code = str(code).zfill(6)
                    if len(code) == 6 and code.isdigit():
                        code_set.add(code)
        except Exception:
            pass

    # 2) fallback: top market-cap by exchange
    if not code_set and FDR_AVAILABLE:
        try:
            market_name = target_market_map[index_key]
            top_n = target_size_map[index_key]
            listing = fdr.StockListing(market_name)
            if not listing.empty and "Code" in listing.columns and "Name" in listing.columns:
                if "Marcap" in listing.columns:
                    listing = listing.sort_values("Marcap", ascending=False)
                listing = listing.head(top_n)
                for _, rr in listing.iterrows():
                    code = str(rr.get("Code", "")).zfill(6)
                    if len(code) == 6 and code.isdigit():
                        code_set.add(code)
        except Exception:
            pass

    # build rows
    for code in sorted(code_set):
        if code in by_code:
            out.append(by_code[code])
        else:
            suffix = ".KQ" if index_key == "KOSDAQ100" else ".KS"
            exch = "KOSDAQ" if index_key == "KOSDAQ100" else "KOSPI"
            out.append(
                {
                    "name": code,
                    "symbol": f"{code}{suffix}",
                    "exchange": exch,
                    "currency": "KRW",
                    "price": "-",
                }
            )

    return dedupe_rows(out, limit=2000)


def get_theme_candidates(theme: str, market: str, limit: int = 5000) -> list[dict[str, str]]:
    if theme == "없음":
        return []

    if market == "KR":
        rows = get_krx_universe()
        seeds = set(THEME_KR_SEEDS.get(theme, []))
        keys = [k.lower() for k in THEME_KEYWORDS.get(theme, [])]
        matched = []

        # Primary path: full KRX universe match
        if rows:
            seed_norm = {s.replace(" ", "").lower() for s in seeds}
            for row in rows:
                name = row["name"]
                lname = name.lower()
                nkey = name.replace(" ", "").lower()
                if (nkey in seed_norm) or any(k in lname for k in keys):
                    matched.append(row)
            return dedupe_rows(matched, limit=limit)

        # Fallback path: when pykrx universe is unavailable on runtime
        # Use seed names + keyword search through Yahoo lookup.
        fallback_rows: list[dict[str, str]] = []
        for seed_name in THEME_KR_SEEDS.get(theme, []):
            seed_matches = search_candidates(seed_name, "KR", max_results=50)
            fallback_rows.extend(seed_matches)

        for k in keys:
            if len(k) >= 2 and not k.isascii():
                key_matches = search_candidates(k, "KR", max_results=50)
                fallback_rows.extend(key_matches)

        return dedupe_rows(fallback_rows, limit=limit)

    rows = get_us_universe()
    seeds = {s.upper() for s in THEME_US_SEEDS.get(theme, [])}
    keys = [k.lower() for k in THEME_KEYWORDS.get(theme, [])]
    matched = []
    for row in rows:
        name = row["name"].lower()
        symbol = row["symbol"].upper()
        if (symbol in seeds) or any(k in name for k in keys):
            matched.append(row)
    return dedupe_rows(matched, limit=limit)


@st.cache_data(show_spinner=False, ttl=600)
def search_candidates(query: str, market: str, max_results: int = 5000) -> list[dict[str, str]]:
    keyword = query.strip()
    if not keyword:
        return []

    key = keyword.replace(" ", "").lower()

    if market == "KR":
        krx_rows = get_krx_universe()
        if krx_rows:
            matched = []
            for row in krx_rows:
                row_key = row["name"].replace(" ", "").lower()
                symbol_key = row["symbol"].replace(".", "").lower()
                if key in row_key or key in symbol_key:
                    matched.append(row)
            matched.sort(key=lambda x: (x["name"].replace(" ", "").lower() != key, x["name"]))
            if matched:
                return matched[:max_results]
    else:
        us_rows = get_us_universe()
        if us_rows:
            matched = []
            for row in us_rows:
                row_key = row["name"].replace(" ", "").lower()
                symbol_key = row["symbol"].lower()
                if key in row_key or key in symbol_key:
                    matched.append(row)
            matched.sort(key=lambda x: (x["symbol"].lower() != key and x["name"].replace(" ", "").lower() != key, x["name"]))
            if matched:
                return matched[:max_results]

    results: list[dict[str, str]] = []
    try:
        quotes = yf.Search(keyword, max_results=20).quotes or []
    except Exception:
        quotes = []

    for q in quotes:
        symbol = str(q.get("symbol", "")).upper()
        name = str(q.get("shortname", "") or q.get("longname", "") or symbol).strip()
        q_type = str(q.get("quoteType", "")).upper()
        exchange = str(q.get("exchDisp", "") or q.get("exchange", "")).strip()
        currency = str(q.get("currency", "")).strip()
        last_price = q.get("regularMarketPrice", "")
        try:
            price_text = f"{float(last_price):.2f}" if last_price not in ("", None) else "-"
        except Exception:
            price_text = "-"
        if not symbol:
            continue

        item = {
            "symbol": symbol,
            "name": name,
            "exchange": exchange or "-",
            "currency": currency or "-",
            "price": price_text,
        }
        if market == "KR":
            if symbol.endswith(".KS") or symbol.endswith(".KQ"):
                results.append(item)
        else:
            if (not symbol.endswith(".KS")) and (not symbol.endswith(".KQ")) and q_type in {"EQUITY", "ETF", ""}:
                results.append(item)

    return dedupe_rows(results, limit=max_results)


def resolve_ticker(raw_input: str, market: str, kr_exchange: str) -> tuple[str, str]:
    query = raw_input.strip()
    if not query:
        return "", "empty"

    query_lower = query.lower()
    if query_lower in NAME_ALIASES:
        return NAME_ALIASES[query_lower], "alias"

    symbol = query.upper()

    if market == "KR" and "." not in symbol and symbol.isdigit() and len(symbol) == 6:
        suffix = ".KS" if kr_exchange == "KOSPI" else ".KQ"
        return f"{symbol}{suffix}", "kr_code"

    key = query.replace(" ", "").lower()

    if market == "KR":
        for row in get_krx_universe():
            row_key = row["name"].replace(" ", "").lower()
            if row_key == key:
                return row["symbol"], "krx_exact"
        for row in get_krx_universe():
            row_key = row["name"].replace(" ", "").lower()
            if key and key in row_key:
                return row["symbol"], "krx_partial"
    else:
        for row in get_us_universe():
            row_name = row["name"].replace(" ", "").lower()
            row_symbol = row["symbol"].lower()
            if key == row_symbol or key == row_name:
                return row["symbol"], "us_exact"
        for row in get_us_universe():
            row_name = row["name"].replace(" ", "").lower()
            row_symbol = row["symbol"].lower()
            if key and (key in row_name or key in row_symbol):
                return row["symbol"], "us_partial"

    if "." in symbol or (symbol.isalnum() and len(symbol) <= 6 and symbol == symbol.upper()):
        return symbol, "direct"

    try:
        search = yf.Search(query, max_results=10)
        quotes = search.quotes or []
    except Exception:
        quotes = []

    if market == "KR":
        for q in quotes:
            sym = str(q.get("symbol", "")).upper()
            if sym.endswith(".KS") or sym.endswith(".KQ"):
                return sym, "search"
    else:
        for q in quotes:
            sym = str(q.get("symbol", "")).upper()
            quote_type = str(q.get("quoteType", "")).upper()
            if (not sym.endswith(".KS")) and (not sym.endswith(".KQ")) and quote_type in {"EQUITY", "ETF", ""}:
                return sym, "search"

    return symbol, "fallback"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def period_to_days(period: str) -> int:
    mapping = {
        "1mo": 35,
        "3mo": 100,
        "6mo": 200,
        "1y": 380,
        "2y": 760,
        "5y": 1900,
    }
    return mapping.get(period, 380)


def yfinance_download_safe(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    except Exception:
        return pd.DataFrame()
    df = normalize_columns(df)
    if df.empty:
        return df
    needed = {"Open", "High", "Low", "Close"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()
    return df


def fetch_krx_ohlcv_pykrx(symbol: str, period: str) -> pd.DataFrame:
    if not KRX_AVAILABLE:
        return pd.DataFrame()
    ticker = symbol.split(".")[0]
    if (not ticker.isdigit()) or len(ticker) != 6:
        return pd.DataFrame()

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=period_to_days(period))
    try:
        df = krx_stock.get_market_ohlcv_by_date(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), ticker)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()
    rename_map = {"시가": "Open", "고가": "High", "저가": "Low", "종가": "Close", "거래량": "Volume"}
    df = df.rename(columns=rename_map)
    for col in ["Open", "High", "Low", "Close"]:
        if col not in df.columns:
            return pd.DataFrame()
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_krx_ohlcv_fdr(symbol: str, period: str) -> pd.DataFrame:
    if not FDR_AVAILABLE:
        return pd.DataFrame()
    ticker = symbol.split(".")[0]
    if (not ticker.isdigit()) or len(ticker) != 6:
        return pd.DataFrame()

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=period_to_days(period))
    try:
        df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()
    needed = ["Open", "High", "Low", "Close"]
    for col in needed:
        if col not in df.columns:
            return pd.DataFrame()
    if "Volume" not in df.columns:
        df["Volume"] = 0
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_price_data(ticker: str, market: str, period: str, interval: str, kr_exchange: str) -> tuple[pd.DataFrame, str, str]:
    tried: list[str] = []
    candidates: list[str] = []

    if market == "KR":
        base = ticker.split(".")[0]
        if base.isdigit() and len(base) == 6:
            candidates.append(f"{base}.KS")
            candidates.append(f"{base}.KQ")
            if kr_exchange == "KOSDAQ":
                candidates = [f"{base}.KQ", f"{base}.KS"]
        candidates.append(ticker.upper())
    else:
        candidates.append(ticker.upper())

    dedup_candidates = []
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            dedup_candidates.append(c)

    for sym in dedup_candidates:
        tried.append(sym)
        df = yfinance_download_safe(sym, period, interval)
        if not df.empty:
            return df, f"yfinance:{sym}", sym

    if market == "KR":
        for sym in dedup_candidates:
            df = fetch_krx_ohlcv_pykrx(sym, period)
            if not df.empty:
                return df, f"pykrx:{sym}(interval=1d)", sym
        for sym in dedup_candidates:
            df = fetch_krx_ohlcv_fdr(sym, period)
            if not df.empty:
                return df, f"fdr:{sym}(interval=1d)", sym

    return pd.DataFrame(), f"failed:{','.join(tried)}", ticker


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["SMA20"] = out["Close"].rolling(20).mean()
    out["SMA60"] = out["Close"].rolling(60).mean()

    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    out["RSI"] = 100 - (100 / (1 + rs))

    rsi_prev = out["RSI"].shift(1)
    out["BuySignal"] = (rsi_prev < 30) & (out["RSI"] >= 30)
    out["SellSignal"] = (rsi_prev > 70) & (out["RSI"] <= 70)
    return out


def run_backtest(df: pd.DataFrame) -> tuple[pd.Series, float, int, float]:
    bt = df.copy()
    bt["Position"] = 0
    bt.loc[bt["BuySignal"], "Position"] = 1
    bt.loc[bt["SellSignal"], "Position"] = 0
    bt["Position"] = bt["Position"].replace(0, pd.NA).ffill().fillna(0)
    bt.loc[bt["SellSignal"], "Position"] = 0
    bt["Position"] = bt["Position"].ffill().fillna(0)

    bt["Return"] = bt["Close"].pct_change().fillna(0)
    bt["StrategyReturn"] = bt["Return"] * bt["Position"].shift(1).fillna(0)
    equity = (1 + bt["StrategyReturn"]).cumprod()
    total_return = (equity.iloc[-1] - 1) * 100

    trade_returns = []
    in_position = False
    entry_price = 0.0
    for _, row in bt.iterrows():
        if (not in_position) and bool(row["BuySignal"]):
            in_position = True
            entry_price = float(row["Close"])
        elif in_position and bool(row["SellSignal"]):
            trade_returns.append((float(row["Close"]) / entry_price) - 1)
            in_position = False

    trade_count = len(trade_returns)
    win_rate = (sum(1 for r in trade_returns if r > 0) / trade_count * 100) if trade_count else 0.0
    return equity, total_return, trade_count, win_rate


def build_forecast(df: pd.DataFrame, model_name: str = "baseline", horizon_days: int = 252) -> dict | None:
    if ML_FORECAST_AVAILABLE and build_ml_forecast is not None:
        return build_ml_forecast(df, model_name=model_name, horizon_days=horizon_days)

    # Fallback when module import fails in some environments.
    close = df["Close"].dropna().astype(float)
    if len(close) < 40:
        return None

    y = close.values
    x = np.arange(len(y), dtype=float)
    w = np.linspace(0.6, 1.4, len(y))
    try:
        slope, intercept = np.polyfit(x, y, 1, w=w)
    except Exception:
        return None

    fx = np.arange(len(y), len(y) + horizon_days, dtype=float)
    future = np.maximum(intercept + slope * fx, 0.01)
    last_idx = pd.Timestamp(df.index[-1])
    if last_idx.tzinfo is not None:
        last_idx = last_idx.tz_localize(None)
    future_dates = pd.bdate_range(last_idx + pd.Timedelta(days=1), periods=horizon_days)
    forecast_path = pd.DataFrame({"Forecast": future}, index=future_dates)

    last_price = float(y[-1])
    ret_1m = (future[min(20, horizon_days - 1)] / last_price - 1) * 100
    ret_2m = (future[min(41, horizon_days - 1)] / last_price - 1) * 100
    ret_3m = (future[min(62, horizon_days - 1)] / last_price - 1) * 100
    ret_6m = (future[min(125, horizon_days - 1)] / last_price - 1) * 100
    ret_12m = (future[min(251, horizon_days - 1)] / last_price - 1) * 100

    if ret_12m >= 8:
        signal = "BUY"
        signal_label = "예상 매수지점"
    elif ret_12m <= -8:
        signal = "SELL"
        signal_label = "예상 매도지점"
    else:
        signal = "HOLD"
        signal_label = "관망"

    return {
        "path": forecast_path,
        "ret_1m": ret_1m,
        "ret_2m": ret_2m,
        "ret_3m": ret_3m,
        "ret_6m": ret_6m,
        "ret_12m": ret_12m,
        "signal": signal,
        "signal_label": signal_label,
        "confidence": 50.0,
        "model": "baseline",
        "mae": np.nan,
        "direction_acc": np.nan,
    }


def build_chart(df: pd.DataFrame, ticker: str, mobile_mode: bool, forecast: dict | None = None):
    if not PLOTLY_AVAILABLE:
        return None
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.68, 0.32],
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing_line_color="#1f6feb",
            increasing_fillcolor="#1f6feb",
            decreasing_line_color="#d93025",
            decreasing_fillcolor="#d93025",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA20"],
            mode="lines",
            name="SMA20",
            line=dict(color="#f59f00", width=2),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["SMA60"],
            mode="lines",
            name="SMA60",
            line=dict(color="#2f9e44", width=2),
        ),
        row=1,
        col=1,
    )

    buy_df = df[df["BuySignal"]]
    sell_df = df[df["SellSignal"]]

    fig.add_trace(
        go.Scatter(
            x=buy_df.index,
            y=buy_df["Low"] * 0.995,
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color="#7b2cbf"),
            name="Buy",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=sell_df.index,
            y=sell_df["High"] * 1.005,
            mode="markers",
            marker=dict(symbol="triangle-down", size=11, color="#ff8f00"),
            name="Sell",
        ),
        row=1,
        col=1,
    )

    if forecast is not None:
        fdf = forecast["path"]
        up = forecast["signal"] == "BUY"
        down = forecast["signal"] == "SELL"
        fc_color = "#9ec5fe" if up else ("#ffc9c9" if down else "#ced4da")
        marker_color = "#1971c2" if up else ("#c92a2a" if down else "#495057")

        fig.add_trace(
            go.Scatter(
                x=fdf.index,
                y=fdf["Forecast"],
                mode="lines",
                name="1~3개월 예측",
                line=dict(color=fc_color, width=3, dash="dot"),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=[df.index[-1]],
                y=[df["Close"].iloc[-1]],
                mode="markers+text",
                name="예측 신호",
                marker=dict(symbol="diamond", size=12, color=marker_color),
                text=[forecast["signal_label"]],
                textposition="top center",
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            mode="lines",
            name="RSI(14)",
            line=dict(color="#00897b", width=2),
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#b71c1c", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#0d47a1", row=2, col=1)

    fig.update_layout(
        title=f"{ticker} Price / Signals",
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        height=620 if mobile_mode else 820,
        legend=dict(orientation="h", y=1.02, x=0.01),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eef2f7")
    fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
    return fig


st.sidebar.header("설정")
user_state = load_user_state()
recent_symbols = user_state.get("recent", [])
favorite_symbols = user_state.get("favorites", [])

market = st.sidebar.selectbox("시장", ["US", "KR"], index=0)
if market == "KR":
    exchange_choice = st.sidebar.selectbox("거래소", ["전체", "KOSPI", "KOSDAQ", "KONEX"], index=0)
    kr_exchange = "KOSDAQ" if exchange_choice == "KOSDAQ" else "KOSPI"
    index_basket_label = st.sidebar.selectbox("대표지수 구성종목", ["없음", "KOSPI 50", "KOSDAQ 100"], index=0)
else:
    exchange_choice = st.sidebar.selectbox("거래소", ["전체", "NASDAQ", "NYSE", "NYSE American", "NYSE Arca", "IEX", "BATS"], index=0)
    kr_exchange = "KOSPI"
    index_basket_label = "없음"

theme_choice = st.sidebar.selectbox("테마 카테고리", THEME_OPTIONS, index=0)

if theme_choice != "없음":
    input_label = "테마 내 회사명 필터(선택)"
    default_value = ""
else:
    input_label = "티커 또는 회사명"
    default_value = ""
user_input = st.sidebar.text_input(input_label, value=default_value).strip()

theme_candidates = filter_candidates_by_exchange(get_theme_candidates(theme_choice, market, limit=5000), market, exchange_choice)
search_base_candidates = filter_candidates_by_exchange(
    search_candidates(user_input, market, max_results=5000) if len(user_input) >= 1 else [],
    market,
    exchange_choice,
)

index_basket_rows: list[dict[str, str]] = []
if market == "KR" and index_basket_label != "없음":
    idx_key = "KOSPI50" if index_basket_label == "KOSPI 50" else "KOSDAQ100"
    index_basket_rows = get_krx_index_constituents(idx_key)
    st.sidebar.caption(f"{index_basket_label} 구성종목 {len(index_basket_rows)}개")

key = user_input.replace(" ", "").lower()
theme_filtered_all: list[dict[str, str]] = []
if theme_choice != "없음":
    base = theme_candidates
    filtered_theme = []
    for row in base:
        row_key = row["name"].replace(" ", "").lower()
        sym_key = row["symbol"].replace(".", "").lower()
        if (not key) or (key in row_key) or (key in sym_key):
            filtered_theme.append(row)
    theme_filtered_all = dedupe_rows(filtered_theme, limit=5000)
    candidates_all = theme_filtered_all
else:
    if key:
        candidates_all = dedupe_rows(search_base_candidates, limit=5000)
    else:
        universe = get_krx_universe() if market == "KR" else get_us_universe()
        universe = filter_candidates_by_exchange(universe, market, exchange_choice)
        candidates_all = dedupe_rows(universe, limit=5000)

if index_basket_rows:
    idx_filtered = []
    for row in index_basket_rows:
        row_key = row["name"].replace(" ", "").lower()
        sym_key = row["symbol"].replace(".", "").lower()
        if (not key) or (key in row_key) or (key in sym_key):
            idx_filtered.append(row)
    candidates_all = dedupe_rows(idx_filtered, limit=5000)

theme_selected_symbol = ""
if theme_choice != "없음" and theme_filtered_all:
    st.sidebar.markdown("**테마 관련회사 선택**")
    st.sidebar.caption(f"테마 필터 후보 총 {len(theme_filtered_all)}개")
    theme_page_size = st.sidebar.selectbox("테마 표시 수", [20, 50, 100], index=1, key="theme_page_size")
    theme_total_pages = max(1, int(np.ceil(len(theme_filtered_all) / theme_page_size)))
    theme_page = int(
        st.sidebar.number_input("테마 페이지", min_value=1, max_value=theme_total_pages, value=1, step=1, key="theme_page")
    )
    t_start = (theme_page - 1) * theme_page_size
    theme_page_rows = theme_filtered_all[t_start : t_start + theme_page_size]
    st.sidebar.caption(f"테마 후보 {len(theme_filtered_all)}개 / 현재 {theme_page}/{theme_total_pages}")
    theme_option_labels = ["선택 안함"] + [
        f"{c['name']} | {c['symbol']} | {c['exchange']}" for c in theme_page_rows
    ]
    theme_choice_label = st.sidebar.selectbox("테마 회사", theme_option_labels, index=0, key="theme_company_select")
    if theme_choice_label != "선택 안함":
        theme_selected_symbol = theme_choice_label.split("|")[1].strip()
        st.sidebar.caption(f"테마 선택 티커: {theme_selected_symbol}")

index_selected_symbol = ""
if index_basket_rows:
    st.sidebar.markdown("**지수 구성종목 선택**")
    index_page_size = st.sidebar.selectbox("지수 표시 수", [20, 50, 100], index=1, key="index_page_size")
    index_total_pages = max(1, int(np.ceil(len(index_basket_rows) / index_page_size)))
    index_page = int(
        st.sidebar.number_input("지수 페이지", min_value=1, max_value=index_total_pages, value=1, step=1, key="index_page")
    )
    i_start = (index_page - 1) * index_page_size
    index_page_rows = index_basket_rows[i_start : i_start + index_page_size]
    st.sidebar.caption(f"지수 후보 {len(index_basket_rows)}개 / 현재 {index_page}/{index_total_pages}")
    index_option_labels = ["선택 안함"] + [
        f"{c['name']} | {c['symbol']} | {c['exchange']}" for c in index_page_rows
    ]
    index_choice_label = st.sidebar.selectbox("지수 회사", index_option_labels, index=0, key="index_company_select")
    if index_choice_label != "선택 안함":
        index_selected_symbol = index_choice_label.split("|")[1].strip()
        st.sidebar.caption(f"지수 선택 티커: {index_selected_symbol}")

selected_symbol = ""
if theme_choice == "없음":
    st.sidebar.caption(f"검색 후보 총 {len(candidates_all)}개")
    page_size = st.sidebar.selectbox("후보 표시 수", [20, 50, 100, 200], index=2)
    total_pages = max(1, int(np.ceil(len(candidates_all) / page_size))) if candidates_all else 1
    candidate_page = int(
        st.sidebar.number_input("후보 페이지", min_value=1, max_value=total_pages, value=1, step=1)
    )
    start_idx = (candidate_page - 1) * page_size
    candidates = candidates_all[start_idx : start_idx + page_size]
    st.sidebar.caption(f"현재 페이지: {candidate_page}/{total_pages}")
else:
    candidates = []

if theme_choice == "없음" and candidates_all and candidates:
    option_labels = [
        f"{c['name']} | {c['symbol']} | {c['exchange']} | {c['currency']} | {c['price']}"
        for c in candidates
    ]
    label_to_symbol = {label: c["symbol"] for label, c in zip(option_labels, candidates)}
    selected_label = st.sidebar.selectbox("자동완성 후보", option_labels, index=0)
    selected_symbol = label_to_symbol[selected_label]
    st.sidebar.caption(f"선택 티커: {selected_symbol}")

quick_symbol = ""
st.sidebar.markdown("**최근 본 종목**")
if recent_symbols:
    for sym in recent_symbols[:10]:
        if st.sidebar.button(f"최근: {sym}", key=f"recent_btn_{sym}"):
            quick_symbol = sym
else:
    st.sidebar.caption("저장된 최근 종목이 없습니다.")

st.sidebar.markdown("**즐겨찾기**")
if favorite_symbols:
    for sym in favorite_symbols[:10]:
        if st.sidebar.button(f"★ {sym}", key=f"fav_btn_{sym}"):
            quick_symbol = sym
else:
    st.sidebar.caption("즐겨찾기 종목이 없습니다.")

candidate_symbol = index_selected_symbol or theme_selected_symbol or selected_symbol
if (not candidate_symbol) and user_input:
    r_ticker, _ = resolve_ticker(user_input, market, kr_exchange)
    candidate_symbol = r_ticker

if candidate_symbol:
    cand_upper = candidate_symbol.upper()
    is_favorite = cand_upper in [x.upper() for x in favorite_symbols]
    fav_label = "즐겨찾기 삭제" if is_favorite else "즐겨찾기 추가"
    if st.sidebar.button(fav_label, key="fav_toggle_btn"):
        favs = [x.upper() for x in favorite_symbols]
        if is_favorite:
            favs = [x for x in favs if x != cand_upper]
        else:
            favs = [cand_upper] + [x for x in favs if x != cand_upper]
        user_state["favorites"] = favs[:50]
        save_user_state(user_state)
        st.rerun()

show_kosdaq_list = False
kosdaq_selected_symbol = ""
if market == "KR":
    kosdaq_rows = [r for r in get_krx_universe() if r.get("exchange") == "KOSDAQ"]
    st.sidebar.caption(f"KOSDAQ 상장사 {len(kosdaq_rows)}개")
    show_kosdaq_list = st.sidebar.toggle("KOSDAQ 전체 목록 표 보기", value=False)
    if kosdaq_rows:
        st.sidebar.markdown("**KOSDAQ 상장사 선택**")
        kosdaq_filter = st.sidebar.text_input("KOSDAQ 회사명 필터", value="", key="kosdaq_filter").strip()
        k_key = kosdaq_filter.replace(" ", "").lower()
        kosdaq_rows = sorted(kosdaq_rows, key=lambda r: (str(r.get("name", "")).lower(), str(r.get("symbol", ""))))
        if k_key:
            k_rows = [
                r
                for r in kosdaq_rows
                if (k_key in r["name"].replace(" ", "").lower()) or (k_key in r["symbol"].replace(".", "").lower())
            ]
        else:
            k_rows = kosdaq_rows
        st.sidebar.caption(f"필터 결과 {len(k_rows)}개")
        if (not k_key) and len(k_rows) > 400:
            st.sidebar.caption("회사명 필터를 입력하면 정확히 찾을 수 있습니다. (초기 400개만 표시)")
            visible_rows = k_rows[:400]
        else:
            visible_rows = k_rows
        options = ["선택 안함"] + [f"{r['name']} | {r['symbol']}" for r in visible_rows]
        picked = st.sidebar.selectbox("KOSDAQ 회사", options, index=0, key="kosdaq_company_select")
        if picked != "선택 안함":
            kosdaq_selected_symbol = picked.split("|")[1].strip()
            st.sidebar.caption(f"KOSDAQ 선택 티커: {kosdaq_selected_symbol} (선택 즉시 조회)")

period = st.sidebar.selectbox("기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
interval = st.sidebar.selectbox("봉 간격", ["1d", "1h"], index=0)
forecast_model_label = st.sidebar.selectbox("예측 모델", list(FORECAST_MODELS.keys()), index=0)
forecast_horizon_months = st.sidebar.selectbox("예측 그래프 기간(개월)", [3, 6, 12], index=2)
mobile_mode = st.sidebar.toggle("모바일 최적화", value=True)

run_requested = st.sidebar.button("분석 시작") or bool(quick_symbol) or bool(kosdaq_selected_symbol)

if show_kosdaq_list:
    with st.expander("KOSDAQ 상장사 전체 목록", expanded=False):
        kdf = pd.DataFrame(kosdaq_rows)
        if kdf.empty:
            st.info("KOSDAQ 상장사 데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
        else:
            for col in ["name", "symbol", "exchange", "currency"]:
                if col not in kdf.columns:
                    kdf[col] = ""
            kdf = kdf[["name", "symbol", "exchange", "currency"]]
            st.dataframe(kdf, use_container_width=True, height=420)

if run_requested:
    if kosdaq_selected_symbol:
        ticker, source = kosdaq_selected_symbol, "kosdaq_list"
    elif quick_symbol:
        ticker, source = quick_symbol, "quick_menu"
    elif index_selected_symbol:
        ticker, source = index_selected_symbol, "index_menu"
    elif theme_selected_symbol:
        ticker, source = theme_selected_symbol, "theme_menu"
    elif selected_symbol:
        ticker, source = selected_symbol, "autocomplete"
    else:
        ticker, source = resolve_ticker(user_input, market, kr_exchange)
    if not ticker:
        st.error("티커 또는 회사명을 입력하세요.")
        st.stop()

    with st.spinner("데이터를 가져오고 지표를 계산하는 중..."):
        raw, data_source, resolved_symbol = fetch_price_data(ticker, market, period, interval, kr_exchange)

    if raw.empty:
        st.error("데이터를 가져오지 못했습니다. 예: 애플/AAPL, 삼성전자/005930, 한화에어로스페이스")
    else:
        df = add_indicators(raw)
        forecast_model = FORECAST_MODELS[forecast_model_label]
        forecast = build_forecast(df, model_name=forecast_model, horizon_days=forecast_horizon_months * 21)

        company_name = get_company_name_by_symbol(resolved_symbol, market)
        if company_name:
            st.success(f"{company_name} ({resolved_symbol}) 분석 완료")
        else:
            st.success(f"{resolved_symbol} 분석 완료")
        st.caption(
            f"입력 해석 방식: {source} | 데이터 소스: {data_source} | 업데이트 시간: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        user_state = add_recent_symbol(user_state, resolved_symbol, limit=30)
        save_user_state(user_state)

        chart = build_chart(df, resolved_symbol, mobile_mode, forecast)
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.warning("현재 서버에 plotly가 없어 간단 차트로 표시합니다. requirements 재배포 후 캔들차트가 복구됩니다.")
            st.line_chart(df[["Close", "SMA20", "SMA60"]], use_container_width=True)

        latest = df.iloc[-1]
        quote_currency = "KRW" if market == "KR" else "USD"
        usdkrw_rate = get_usdkrw_rate()
        krw_value = convert_to_krw(float(latest["Close"]), quote_currency, usdkrw_rate)
        if bool(latest["BuySignal"]):
            signal_text = "매수"
        elif bool(latest["SellSignal"]):
            signal_text = "매도"
        else:
            signal_text = "관망"

        if mobile_mode:
            st.metric("현재가", f"{latest['Close']:.2f}")
            if krw_value is not None:
                st.metric("원화 환산가", f"{krw_value:,.0f} KRW")
            st.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            st.metric("최신 신호", signal_text)
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("현재가", f"{latest['Close']:.2f}")
            col2.metric("원화 환산가", f"{krw_value:,.0f} KRW" if krw_value is not None else "N/A")
            col3.metric("RSI(14)", f"{latest['RSI']:.2f}" if pd.notna(latest["RSI"]) else "N/A")
            col4.metric("최신 신호", signal_text)

        if forecast is not None:
            p1, p2, p3, p4, p5 = st.columns(5)
            p1.metric("예상 수익률(1개월)", f"{forecast['ret_1m']:.2f}%")
            p2.metric("예상 수익률(2개월)", f"{forecast['ret_2m']:.2f}%")
            p3.metric("예상 수익률(3개월)", f"{forecast['ret_3m']:.2f}%")
            p4.metric("예상 수익률(6개월)", f"{forecast.get('ret_6m', np.nan):.2f}%")
            p5.metric("예상 수익률(1년)", f"{forecast.get('ret_12m', np.nan):.2f}%")
            st.caption(f"예측 신호: {forecast['signal_label']} | 추정 신뢰도: {forecast['confidence']:.1f}%")

            base_price = float(latest["Close"])
            r1 = base_price * (forecast["ret_1m"] / 100.0)
            r2 = base_price * (forecast["ret_2m"] / 100.0)
            r3 = base_price * (forecast["ret_3m"] / 100.0)
            r6 = base_price * (forecast.get("ret_6m", np.nan) / 100.0)
            r12 = base_price * (forecast.get("ret_12m", np.nan) / 100.0)
            a1, a2, a3, a4, a5 = st.columns(5)
            a1.metric("예상 손익(1M)", f"{r1:,.2f}")
            a2.metric("예상 손익(2M)", f"{r2:,.2f}")
            a3.metric("예상 손익(3M)", f"{r3:,.2f}")
            a4.metric("예상 손익(6M)", f"{r6:,.2f}" if pd.notna(r6) else "N/A")
            a5.metric("예상 손익(1Y)", f"{r12:,.2f}" if pd.notna(r12) else "N/A")
            if pd.notna(forecast.get("mae", np.nan)):
                m1, m2 = st.columns(2)
                m1.metric("모델 MAE(일수익률)", f"{forecast['mae']:.3f}%")
                m2.metric("방향 정확도", f"{forecast.get('direction_acc', np.nan):.1f}%")

        equity, total_return, trade_count, win_rate = run_backtest(df)

        if mobile_mode:
            st.metric("백테스트 수익률", f"{total_return:.2f}%")
            st.metric("거래 횟수", f"{trade_count}")
            st.metric("승률", f"{win_rate:.1f}%")
        else:
            b1, b2, b3 = st.columns(3)
            b1.metric("백테스트 수익률", f"{total_return:.2f}%")
            b2.metric("거래 횟수", f"{trade_count}")
            b3.metric("승률", f"{win_rate:.1f}%")

        st.subheader("전략 누적수익 곡선")
        equity_df = equity.to_frame(name="Equity")
        st.line_chart(equity_df, use_container_width=True)

        st.subheader("최근 신호")
        signal_table = df.loc[df["BuySignal"] | df["SellSignal"], ["Close", "RSI", "BuySignal", "SellSignal"]].tail(10)
        st.dataframe(signal_table, use_container_width=True)
else:
    st.info(
        "왼쪽에서 시장/회사명(또는 티커)을 입력한 뒤 '분석 시작'을 누르세요. 예: 애플, 삼성전자, 한화에어로스페이스, AAPL, 005930, 로봇, 방산, 반도체"
    )





